#!/usr/bin/env python3
import argparse, json, re, subprocess, time, tempfile
from pathlib import Path

import yaml
from rich.progress import Progress

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "_data"
TASKS_DIR = DATA_DIR / "tasks"
RESULTS_PATH = DATA_DIR / "results.json"

# -------- Parsing helpers --------
# Float like 0.123, 1, .5, 1e-3, -2.5E+06
FLOAT = r"([+-]?(?:\d+\.\d+|\d+|\.\d+)(?:[eE][+-]?\d+)?)"

# Mean label could be "Mean", "After Mean", "Average", "Avg"
RE_MEAN = re.compile(rf"(?i)\b(?:after\s+)?(?:mean|average|avg)\b\s*[:=]\s*{FLOAT}")
# Std label could be "Std", "Std Dev", "SD", "StdDev", "Std Deviation"
RE_STD  = re.compile(rf"(?i)\b(?:std(?:\.|\s*dev)?|sd|stddev|std\s*deviation)\b\s*[:=]\s*{FLOAT}")

# PERF block: prefer the LAST PERF_START..PERF_END block if present
RE_PERF_BLOCK = re.compile(r"(?is)PERF_START:\s*(.*?)\s*PERF_END:")

def extract_scope(text: str) -> str:
    if not text:
        return ""
    blocks = RE_PERF_BLOCK.findall(text)
    if blocks:
        return blocks[-1]
    return text

def parse_mean_std(text: str):
    scope = extract_scope(text)
    means = RE_MEAN.findall(scope)
    stds  = RE_STD.findall(scope)
    if not means or not stds:
        # fallback to whole text
        means = RE_MEAN.findall(text or "")
        stds  = RE_STD.findall(text or "")
    if not means or not stds:
        return None, None
    try:
        return float(means[-1]), float(stds[-1])
    except Exception:
        return None, None

# -------- IO helpers --------
def load_tasks():
    tasks = []
    for p in sorted(TASKS_DIR.glob("*.yml")):
        with open(p, "r", encoding="utf-8") as f:
            d = yaml.safe_load(f)
            if not d:
                continue
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
    # Use shell so templates with pipes work; capture combined stdout/stderr
    out = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return out.stdout

def upsert_result(all_results, rec):
    for i, r in enumerate(all_results):
        if r.get("id") == rec["id"]:
            all_results[i] = rec
            return
    all_results.append(rec)

def render(cmd_template: str, *, id, base_image=None, human_image=None, llm_image=None, workload_py=None):
    return cmd_template.format(
        id=id,
        base_image=base_image or "",
        human_image=human_image or "",
        llm_image=llm_image or "",
    ).replace("<WORKLOAD_PY>", str(workload_py))

# -------- Core runner --------
def run_variant(task, variant, workload_py):
    """
    Returns: (mean, std, info)
      - info is a short string for logging ('OK', 'skipped (placeholder)', 'parse failed', etc.)
    """
    docker = task.get("docker", {})
    id = task["id"]
    cmds = docker.get("commands", {})

    if variant == "base":
        tmpl = cmds.get("run_base")
        img  = docker.get("base_image")

    elif variant == "human":
        tmpl = cmds.get("run_human")
        img  = docker.get("human_image")
        # Guard/fallback: enforce correct order = chmod -> git apply -> /perf.sh
        desired = (
            "docker run --rm --platform linux/amd64 --name bench_{id}_human "
            "--mount type=bind,src=<WORKLOAD_PY>,dst=/tmp/workload.py "
            "{human_image} /bin/bash -lc "
            "'chmod +x /perf.sh && git apply /tmp/patch.diff && /perf.sh' 2>&1"
        )
        if (not tmpl) or ("/perf.sh && git apply" in tmpl) or ("git apply -q" in tmpl):
            tmpl = desired

    elif variant == "llm":
        tmpl = cmds.get("run_llm")
        img  = docker.get("llm_image")
        if not img or str(img).upper().startswith("PLACEHOLDER"):
            return None, None, "skipped (placeholder)"
    else:
        raise ValueError("unknown variant")

    if not tmpl:
        return None, None, f"missing command template for {variant}"

    cmd = render(
        tmpl,
        id=id,
        base_image=docker.get("base_image"),
        human_image=docker.get("human_image"),
        llm_image=docker.get("llm_image"),
        workload_py=workload_py,
    )
    text = run_cmd(cmd)
    mean, std = parse_mean_std(text)
    if mean is None or std is None:
        return None, None, "parse failed"
    return mean, std, "OK"

def p(v):
    # print-friendly (no forced rounding)
    return "—" if v is None else str(v)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="Run only these task ids")
    ap.add_argument("--collect-stats", action="store_true",
                    help="(placeholder) collect docker stats [not implemented in MVP]")
    ap.add_argument("--mode", choices=["quick","resume"], default="quick")
    args = ap.parse_args()

    tasks = load_tasks()
    if args.only:
        only = set(args.only)
        tasks = [t for t in tasks if t.get("id") in only]
    if not tasks:
        print("No tasks found.")
        return

    results = load_results()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with Progress() as progress:
        task_prog = progress.add_task("[cyan]Running tasks...", total=len(tasks))
        for t in tasks:
            id = t["id"]
            workload_code = (t.get("workload") or {}).get("code", "")
            if not workload_code.strip():
                progress.console.print(f"[yellow]{id}[/yellow] has empty workload.code; skipping")
                progress.advance(task_prog)
                continue

            # Prepare workload.py in a temp dir
            with tempfile.TemporaryDirectory() as td:
                wpy = Path(td) / "workload.py"
                wpy.write_text(workload_code, encoding="utf-8")

                before_mean = before_std = None
                human_mean = human_std = None
                llm_mean = llm_std = None

                # Base
                m, s, info = run_variant(t, "base", wpy)
                before_mean, before_std = m, s
                progress.console.print(f"[{id}] base  : mean={p(m)} std={p(s)} ({info})")

                # Human
                m, s, info = run_variant(t, "human", wpy)
                human_mean, human_std = m, s
                progress.console.print(f"[{id}] human : mean={p(m)} std={p(s)} ({info})")

                # LLM
                m, s, info = run_variant(t, "llm", wpy)
                llm_mean, llm_std = m, s
                progress.console.print(f"[{id}] llm   : mean={p(m)} std={p(s)} ({info})")

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

                # ---- Improvements (%), negative = faster (better) ----
                def calc_impr(after_mean, before_mean):
                    try:
                        if after_mean is None or before_mean is None or before_mean == 0:
                            return None
                        return (after_mean / before_mean - 1) * 100.0
                    except Exception:
                        return None

                rec["human_improvement"] = calc_impr(
                    rec["after_human"]["mean"] if rec["after_human"] else None,
                    rec["before"]["mean"] if rec["before"] else None
                )
                rec["LLM_improvement"] = calc_impr(
                    rec["after_llm"]["mean"] if rec["after_llm"] else None,
                    rec["before"]["mean"] if rec["before"] else None
                )

                # (Backward-compat fields; safe to remove later if not needed)
                rec["speedup_human"] = (
                    rec["before"]["mean"] / rec["after_human"]["mean"]
                    if rec.get("before") and rec.get("after_human") and
                       rec["before"]["mean"] and rec["after_human"]["mean"] else None
                )
                rec["speedup_llm"] = (
                    rec["before"]["mean"] / rec["after_llm"]["mean"]
                    if rec.get("before") and rec.get("after_llm") and
                       rec["before"]["mean"] and rec["after_llm"]["mean"] else None
                )

                # LLM better?
                if rec["after_human"] and rec["after_llm"] and \
                   rec["after_human"]["mean"] is not None and rec["after_llm"]["mean"] is not None:
                    hm = rec["after_human"]["mean"]
                    lm = rec["after_llm"]["mean"]
                    eps = 1e-9
                    if lm + eps < hm:
                        rec["comparison"]["llm_better"] = "YES"
                    elif hm + eps < lm:
                        rec["comparison"]["llm_better"] = "NO"
                    else:
                        rec["comparison"]["llm_better"] = "TIE"
                elif rec["status"].get("llm","").upper() in ["COMING_SOON","PENDING"] or \
                     str(t.get("docker",{}).get("llm_image","")).upper().startswith("PLACEHOLDER"):
                    rec["comparison"]["llm_better"] = "COMING_SOON"
                else:
                    rec["comparison"].setdefault("llm_better","UNKNOWN")

                upsert_result(results, rec)

            progress.advance(task_prog)

    save_results(results)
    print(f"Done. Wrote {RESULTS_PATH}")

if __name__ == "__main__":
    main()

