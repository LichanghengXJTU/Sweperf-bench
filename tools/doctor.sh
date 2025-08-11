#!/usr/bin/env bash
set -e

echo "==> Docker version"
docker --version || { echo "Docker not found"; exit 1; }

echo "==> Docker hello-world (may download image)"
docker run --rm hello-world || { echo "Docker hello-world failed"; exit 1; }

echo "==> Disk space (df -h)"
df -h

echo "OK: environment looks sane."

