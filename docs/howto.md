---
layout: default
title: How to
nav_order: 4
---

# How to Reproduce

## Prerequisites
- Docker (Desktop is fine)
- Python 3.9+

## Local Runner
```bash
pip install -r tools/requirements.txt
python tools/bench.py --only pandas-dev__pandas-38248

