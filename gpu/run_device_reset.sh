#!/usr/bin/env bash
# Functional schedules only. No timing or throughput experiment.
set -euo pipefail
case "${ANNS_GPU_INDEX:-0}" in 0|1) ;; *) echo "invalid GPU index"; exit 2;; esac
archive=$(mktemp /tmp/anns-device.XXXXXX.tgz)
trap 'rm -f "$archive"' EXIT
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='.git' --exclude='__pycache__' -czf "$archive" CMakeLists.txt pins.json src gpu/*.cu gpu/*.h gpu/*.py scripts tests vendor/EventLab vendor/HBXim
remote=$(ssh cloudsys01.engr.uconn.edu 'mktemp -d /tmp/anns-device.XXXXXX')
scp "$archive" "cloudsys01.engr.uconn.edu:$remote/source.tgz"
ssh cloudsys01.engr.uconn.edu "bash -s -- '$remote' '${ANNS_GPU_INDEX:-0}'" <<'REMOTE'
set -euo pipefail
cd "$1"
ANNS_GPU_INDEX="$2"
case "$ANNS_GPU_INDEX" in 0|1) ;; *) echo "invalid GPU index"; exit 2;; esac
tar xzf source.tgz
cmake -S . -B build -DANNS_CUDA_VALIDATION=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc >configure.txt 2>&1
cmake --build build --target device_reset_cuda device_reset_probe -j4 >build.txt 2>&1
gpu_uuid=$(nvidia-smi -i "${ANNS_GPU_INDEX:-0}" --query-gpu=uuid --format=csv,noheader)
nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | awk -F, -v id="$gpu_uuid" '$1 == id {print $2}' >processes.txt
test ! -s processes.txt || { echo 'Selected GPU busy'; exit 2; }
nvidia-smi -i "${ANNS_GPU_INDEX:-0}" --query-gpu=name,driver_version,uuid --format=csv >device.csv
/usr/local/cuda/bin/nvcc --version >compiler.txt
sha256sum src/device_reset_probe.cpp src/reset_device.hpp src/eventlab_page_group.hpp src/eventlab_page_writeback.hpp src/versioned_pages.hpp gpu/race_backend.cu gpu/race_backend.h tests/device_reset_diff.py pins.json >sources.sha256
CUDA_VISIBLE_DEVICES="$ANNS_GPU_INDEX" python3 tests/device_reset_diff.py ./build/device_reset_cuda cuda-evidence >cuda-report.txt 2>&1
python3 tests/device_reset_diff.py ./build/device_reset_probe cpu-evidence >cpu-report.txt 2>&1
g++ -std=c++20 -fsanitize=address,undefined -fno-omit-frame-pointer -g -Ibuild/eventlab-overlay/include src/device_reset_probe.cpp build/eventlab/libhbf_eventlab.a -o sanitized
python3 tests/device_reset_diff.py ./sanitized sanitizer-evidence >sanitizer-report.txt 2>&1
cat cuda-report.txt cpu-report.txt sanitizer-report.txt
REMOTE
printf 'Remote evidence: %s\n' "$remote"
