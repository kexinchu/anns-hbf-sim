#!/usr/bin/env bash
# Run from repository root. Functional validation only; never changes GPU state.
set -euo pipefail
archive=$(mktemp /tmp/anns-wire.XXXXXX.tgz)
trap 'rm -f "$archive"' EXIT
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='.git' --exclude='__pycache__' -czf "$archive" CMakeLists.txt pins.json src gpu/*.cu gpu/*.h gpu/*.py scripts tests vendor/EventLab vendor/HBXim
remote=$(ssh cloudsys01.engr.uconn.edu 'mktemp -d /tmp/anns-wire.XXXXXX')
scp "$archive" "cloudsys01.engr.uconn.edu:$remote/source.tgz"
ssh cloudsys01.engr.uconn.edu "bash -s -- '$remote'" <<'REMOTE'
set -euo pipefail
cd "$1"
tar xzf source.tgz
cmake -S . -B build -DANNS_CUDA_VALIDATION=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc >configure.txt 2>&1
cmake --build build --target anns_loop_cuda page_wire_probe page_writeback_contract -j4 >build.txt 2>&1
gpu_uuid=$(nvidia-smi -i 1 --query-gpu=uuid --format=csv,noheader)
nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | awk -F, -v id="$gpu_uuid" '$1 == id {print $2}' >processes.txt
test ! -s processes.txt || { echo 'GPU1 busy: no GPU test launched'; exit 2; }
nvidia-smi -i 1 --query-gpu=name,driver_version,uuid --format=csv >device.csv
/usr/local/cuda/bin/nvcc --version >compiler.txt
sha256sum src/anns_loop.cpp src/versioned_pages.hpp src/eventlab_page_writeback.hpp src/page_wire_probe.cpp src/page_writeback_contract.cpp gpu/page_backend.cu gpu/page_backend.h tests/verify_wire_cuda.py tests/page_wire_diff.py pins.json >sources.sha256
CUDA_VISIBLE_DEVICES=1 python3 tests/verify_wire_cuda.py ./build/anns_loop_cuda cuda-evidence CUDA >cuda-report.txt 2>&1
python3 tests/page_wire_diff.py ./build/page_wire_probe wire-evidence >wire-report.txt 2>&1
./build/page_writeback_contract >contract-report.txt 2>&1
cat cuda-report.txt wire-report.txt contract-report.txt
REMOTE
printf 'Remote evidence: %s\n' "$remote"
