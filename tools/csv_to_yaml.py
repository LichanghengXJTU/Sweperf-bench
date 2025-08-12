#!/usr/bin/env python3
import argparse, csv
from pathlib import Path
import yaml

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True, help="Directory to write YAML files")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            iid = row.get("instance_id") or row.get("id")
            if not iid:
                print("skip a row without instance_id")
                continue
            repo = row.get("repo","")
            org, name = (repo.split("/",1)+[""])[:2] if "/" in repo else ("", repo)

            y = {
                "id": iid,
                "status": {"human": (row.get("status") or "PENDING"), "llm": "COMING_SOON"},
                "comparison": {"llm_better": "COMING_SOON"},
                "repo": {
                    "org": org, "name": name,
                    "url": f"https://github.com/{repo}" if "/" in repo else "",
                    "pull_request": row.get("pull_request_link") or "",
                    "base_commit": row.get("base_commit") or "",
                    "created_at": row.get("created_at") or "",
                    "version": row.get("version") or ""
                },
                "workload": {
                    "language": "python",
                    "code": row.get("workload") or ""
                },
                "docker": {
                    "base_image": row.get("base_docker_image") or "",
                    "human_image": row.get("annotate_dockerhub_image") or "",
                    "llm_image": "PLACEHOLDER",
                    "commands": {
                        "run_base": "docker run --rm --name bench_{id}_base --mount type=bind,src=<WORKLOAD_PY>,dst=/tmp/workload.py {base_image} /bin/bash -lc 'python /tmp/workload.py' 2>&1",
                        "run_human": "docker run --rm --platform linux/amd64 --name bench_{id}_human --mount type=bind,src=<WORKLOAD_PY>,dst=/tmp/workload.py {human_image} /bin/bash -lc 'chmod +x /perf.sh && git apply /tmp/patch.diff && /perf.sh' 2>&1",
                        "run_llm": "echo 'LLM image not available yet for {id}. Please fill docker.llm_image.'"
                    }
                },
                "metrics": {
                    "reducer": "mean_std",
                    "parse_regex": {
                        "mean": r"(?i)\bMean:\s*([0-9.]+)",
                        "std":  r"(?i)(Std Dev|SD):\s*([0-9.]+)"
                    }
                },
                "notes": {
                    "user_notes": row.get("notes") or "",
                    "mike_notes": row.get("mike_notes") or ""
                },
                "meta": {
                    "num_covering_tests": row.get("num_covering_tests")
                }
            }

            with open(out_dir / f"{iid}.yml", "w", encoding="utf-8") as wf:
                yaml.safe_dump(y, wf, sort_keys=False, allow_unicode=True)

    print(f"Wrote YAML files to {out_dir}")

if __name__ == "__main__":
    main()
