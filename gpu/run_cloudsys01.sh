#!/usr/bin/env bash
# Run from repository root. Does not alter GPU state or run throughput benchmarks.
set -euo pipefail
remote=$(ssh cloudsys01.engr.uconn.edu 'mktemp -d /tmp/anns-cuda-recovery.XXXXXX')
ssh cloudsys01.engr.uconn.edu "mkdir -p '$remote/gpu' '$remote/src'"
scp gpu/anns_recovery.cu gpu/verify_recovery.py "cloudsys01.engr.uconn.edu:$remote/gpu/"
scp src/read_recovery.hpp src/versioned_pages.hpp "cloudsys01.engr.uconn.edu:$remote/src/"
ssh cloudsys01.engr.uconn.edu "bash -s -- '$remote'" <<'REMOTE'
set -euo pipefail
cd "$1"
/usr/local/cuda/bin/nvcc -std=c++17 -O2 -arch=sm_86 gpu/anns_recovery.cu -o anns_recovery >build.log 2>&1
gpu_uuid=$(nvidia-smi -i 1 --query-gpu=uuid --format=csv,noheader)
nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | awk -F, -v id="$gpu_uuid" '$1 == id {print $2}' >processes.txt
test ! -s processes.txt || { echo 'GPU1 busy: no test launched'; exit 2; }
/usr/local/cuda/bin/nvcc --version >compiler.txt
sha256sum gpu/anns_recovery.cu gpu/verify_recovery.py src/read_recovery.hpp src/versioned_pages.hpp >sources.sha256
nvidia-smi -i 1 --query-gpu=name,driver_version,ecc.mode.current --format=csv >device.csv
CUDA_VISIBLE_DEVICES=1 python3 gpu/verify_recovery.py ./anns_recovery evidence >report.txt 2>&1
cat report.txt
REMOTE
printf 'Remote evidence: %s\n' "$remote"
