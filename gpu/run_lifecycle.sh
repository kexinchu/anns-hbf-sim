#!/usr/bin/env bash
set -euo pipefail
remote=$(ssh cloudsys01.engr.uconn.edu 'mktemp -d /tmp/anns-lifecycle.XXXXXX')
ssh cloudsys01.engr.uconn.edu "mkdir -p '$remote/gpu' '$remote/src'"
scp gpu/page_lifecycle.cu gpu/verify_lifecycle.py "cloudsys01.engr.uconn.edu:$remote/gpu/"
scp src/versioned_pages.hpp "cloudsys01.engr.uconn.edu:$remote/src/"
ssh cloudsys01.engr.uconn.edu "bash -s -- '$remote'" <<'REMOTE'
set -euo pipefail
cd "$1"
/usr/local/cuda/bin/nvcc -std=c++17 -O2 -arch=sm_86 -Xcompiler -pthread gpu/page_lifecycle.cu -o page_lifecycle >build.log 2>&1
gpu_uuid=$(nvidia-smi -i 1 --query-gpu=uuid --format=csv,noheader)
nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | awk -F, -v id="$gpu_uuid" '$1 == id {print $2}' >processes.txt
test ! -s processes.txt || { echo 'GPU1 busy'; exit 2; }
/usr/local/cuda/bin/nvcc --version >compiler.txt
nvidia-smi -i 1 --query-gpu=name,driver_version,ecc.mode.current --format=csv >device.csv
sha256sum gpu/page_lifecycle.cu gpu/verify_lifecycle.py src/versioned_pages.hpp >sources.sha256
CUDA_VISIBLE_DEVICES=1 python3 gpu/verify_lifecycle.py ./page_lifecycle evidence >report.txt 2>&1
cat report.txt
REMOTE
printf 'Remote evidence: %s\n' "$remote"
