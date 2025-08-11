<<<<<<< HEAD
# Sweperf-bench
Evaluate performance improvements of human-written and LLM-generated patches on real-world OSS tasks, using reproducible Docker images and simple, inspectable workloads.
=======
# SWEPerf LLM Bench

Evaluate performance improvements of human-written and LLM-generated patches on real-world OSS tasks, using reproducible Docker images and simple, inspectable workloads.

- **What this is:** A lean, data-driven benchmark site (GitHub Pages) plus tiny local tools (Python + Docker) to run, compare, and report results.
- **What this is not:** A heavy web service. Everything is static and reproducible.

## TL;DR — Quick Start

1. **Prerequisites**
   - Docker (Desktop is fine). Verify with `docker run hello-world`.
   - Python 3.9+ (3.10+ recommended).

2. **Run a demo task (human patch only)**
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

>>>>>>> a13669c (Initial local import)
