#!/usr/bin/env python3
import argparse, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

import yaml
from rich.progress import Progress

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "_data"
TASKS_DIR = DATA_DIR / "tasks"
RESULTS_PATH = DATA_DIR / "results.json"

RE_MEAN = re.compile(r"(?i)\bMean:\s*([0-9.]+)")
RE_STD  = re.compile(r"(?i)(Std Dev|SD):\s*([0-9.]+)")

def load_tasks():
    tasks = []
    for p in sorted(TASKS_DIR.glob("*.yml")):
        with open(p, "r", encoding="utf-8") as f:
            d = yaml.safe_load(f)
            if not d: continue
            tasks.append(d)
    return tasks

def load_results():
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_results(records):
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, sort_keys=False)

def run_cmd(cmd: str) -> str:
    # Use bash -lc to allow pipes if present
    out = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return out.stdout

def parse_mean_std(text: str):
    m = RE_MEAN.search(text)
    s = RE_STD.search(text)
    if not m or not s:
        return None, None
    return float(m.group(1)), float(s.group(2))

def upsert_result(all_results, rec):
    # Replace by id
    found = False
    for i, r in enumerate(all_results):
        if r.get("id") == rec["id"]:
            all_results[i] = rec
            found = True
            break
    if not found:
        all_results.append(rec)

def render(cmd_template: str, *, id, base_image=None, human_image=None, llm_image=None, workload_py=None):
    return cmd_template.format(
        id=id,
        base_image=base_image or "",
        human_image=human_image or "",
        llm_image=llm_image or "",
    ).replace("<WORKLOAD_PY>", str(workload_py))

def run_variant(task, variant, workload_py):
    docker = task.get("docker", {})
    id = task["id"]
    cmds = docker.get("commands", {})
    if variant == "base":
        tmpl = cmds.get("run_base")
        img  = docker.get("base_image")
    elif variant == "human":
        tmpl = cmds.get("run_human")
        img  = docker.get("human_image")
    elif variant == "llm":
        tmpl = cmds.get("run_llm")
        img  = docker.get("llm_image")
        if not img or str(img).upper().startswith("PLACEHOLDER"):
            return None, None, "LLM image placeholder"
    else:
        raise ValueError("unknown variant")

    if not tmpl:
        return None, None, f"missing command template for {variant}"

    cmd = render(tmpl, id=id, base_image=docker.get("base_image"),
                 human_image=docker.get("human_image"),
                 llm_image=docker.get("llm_image"),
                 workload_py=workload_py)
    text = run_cmd(cmd)
    mean, std = parse_mean_std(text)
    return mean, std, text[-2000:]  # keep last 2k chars for debugging

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="Run only these task ids")
    ap.add_argument("--collect-stats", action="store_true", help="(optional) collect docker stats [not implemented in MVP]")
    ap.add_argument("--mode", choices=["quick","resume"], default="quick")
    args = ap.parse_args()

    tasks = load_tasks()
    if args.only:
        tasks = [t for t in tasks if t.get("id") in set(args.only)]
    if not tasks:
        print("No tasks found.")
        return

    results = load_results()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with Progress() as progress:
        task_prog = progress.add_task("[cyan]Running tasks...", total=len(tasks))
        for t in tasks:
            id = t["id"]
            # write workload code to a temp py
            workload_code = (t.get("workload") or {}).get("code", "")
            if not workload_code.strip():
                progress.console.print(f"[yellow]{id}[/yellow] has empty workload.code; skipping")
                progress.advance(task_prog)
                continue
            with tempfile.TemporaryDirectory() as td:
                wpy = Path(td) / "workload.py"
                wpy.write_text(workload_code, encoding="utf-8")

                before_mean = before_std = None
                human_mean = human_std = None
                llm_mean = llm_std = None

                for variant in ["base","human","llm"]:
                    m, s, tail = run_variant(t, variant, wpy)
                    if variant == "base":
                        before_mean, before_std = m, s
                    elif variant == "human":
                        human_mean, human_std = m, s
                    elif variant == "llm":
                        llm_mean, llm_std = m, s

                rec = {
                    "id": id,
                    "before": {"mean": before_mean, "std": before_std} if before_mean is not None else None,
                    "after_human": {"mean": human_mean, "std": human_std} if human_mean is not None else None,
                    "after_llm": {"mean": llm_mean, "std": llm_std} if llm_mean is not None else None,
                    "status": t.get("status", {}),
                    "comparison": t.get("comparison", {}),
                    "stats": {"collect": False, "cpu_p95": None, "mem_max_mb": None},
                    "updated_at": now_iso
                }

                # speedups if available
                if rec["before"] and rec["after_human"]:
                    try:
                        rec["speedup_human"] = rec["before"]["mean"] / rec["after_human"]["mean"]
                    except Exception:
                        rec["speedup_human"] = None
                else:
                    rec["speedup_human"] = None
                if rec["before"] and rec["after_llm"]:
                    try:
                        rec["speedup_llm"] = rec["before"]["mean"] / rec["after_llm"]["mean"]
                    except Exception:
                        rec["speedup_llm"] = None
                else:
                    rec["speedup_llm"] = None

                # set comparison.llm_better automatically if both exist
                if rec["after_human"] and rec["after_llm"]:
                    hm = rec["after_human"]["mean"]
                    lm = rec["after_llm"]["mean"]
                    if hm is None or lm is None:
                        pass
                    else:
                        eps = 1e-9
                        if lm + eps < hm:
                            rec["comparison"]["llm_better"] = "YES"
                        elif hm + eps < lm:
                            rec["comparison"]["llm_better"] = "NO"
                        else:
                            rec["comparison"]["llm_better"] = "TIE"
                elif rec["status"].get("llm","").upper() in ["COMING_SOON","PENDING"] or str(t.get("docker",{}).get("llm_image","")).upper().startswith("PLACEHOLDER"):
                    rec["comparison"]["llm_better"] = "COMING_SOON"
                else:
                    rec["comparison"].setdefault("llm_better","UNKNOWN")

                upsert_result(results, rec)
            progress.advance(task_prog)

    save_results(results)
    print(f"Done. Wrote {RESULTS_PATH}")

if __name__ == "__main__":
    main()

