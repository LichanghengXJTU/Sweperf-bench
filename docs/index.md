---
layout: default
title: Home
nav_order: 1
---

# SWEPerf LLM Bench

A simple, reproducible benchmark of human vs. LLM patches on real OSS workloads.

- **One-minute demo** below
- **Tasks** for the full list
- **Results** for aggregated numbers
- **How to** for reproduction steps

## One-minute demo

```bash
# Base (no patch)
docker run --rm --name bench_pandas-dev__pandas-38248_base \
  --mount type=bind,src=$(pwd)/docs/_data/tasks/workload_example.py,dst=/tmp/workload.py \
  docker.io/sweperf/sweperf:pandas-dev__pandas-38248 \
  /bin/bash -lc 'python /tmp/workload.py' 2>&1

# Human patch
docker run --rm --name bench_pandas-dev__pandas-38248_human \
  --mount type=bind,src=$(pwd)/docs/_data/tasks/workload_example.py,dst=/tmp/workload.py \
  docker.io/sweperf/sweperf_annotate:pandas-dev__pandas-38248 \
  /bin/bash -lc 'chmod +x /perf.sh && /perf.sh && python /tmp/workload.py' 2>&1

