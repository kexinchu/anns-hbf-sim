#!/usr/bin/env bash
# Functional schedules only. No timing or throughput experiment.
set -euo pipefail
case "${ANNS_GPU_INDEX:-0}" in 0|1) ;; *) echo "invalid GPU index"; exit 2;; esac
archive=$(mktemp /tmp/anns-driver.XXXXXX.tgz)
trap 'rm -f "$archive"' EXIT
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='.git' --exclude='__pycache__' -czf "$archive" CMakeLists.txt pins.json src gpu/*.cu gpu/*.h gpu/*.py scripts tests vendor/EventLab vendor/HBXim
remote=$(ssh cloudsys01.engr.uconn.edu 'mktemp -d /tmp/anns-driver.XXXXXX')
printf 'Remote build directory: %s\n' "$remote"
scp "$archive" "cloudsys01.engr.uconn.edu:$remote/source.tgz"
ssh cloudsys01.engr.uconn.edu "bash -s -- '$remote' '${ANNS_GPU_INDEX:-0}'" <<'REMOTE'
set -euo pipefail
cd "$1"
ANNS_GPU_INDEX="$2"
case "$ANNS_GPU_INDEX" in 0|1) ;; *) echo "invalid GPU index"; exit 2;; esac
tar xzf source.tgz
cmake -S . -B build -DANNS_CUDA_VALIDATION=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc >configure.txt 2>&1
cmake --build build --target driver_reset_cuda driver_reset_probe -j4 >build.txt 2>&1
gpu_uuid=$(nvidia-smi -i "${ANNS_GPU_INDEX:-0}" --query-gpu=uuid --format=csv,noheader)
nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | awk -F, -v id="$gpu_uuid" '$1 == id {print $2}' >processes.txt
test ! -s processes.txt || { echo 'Selected GPU busy'; exit 2; }
nvidia-smi -i "${ANNS_GPU_INDEX:-0}" --query-gpu=name,driver_version,uuid --format=csv >device.csv
/usr/local/cuda/bin/nvcc --version >compiler.txt
sha256sum src/driver_reset_probe.cpp scripts/prepare_eventlab.py scripts/driver_reset_overlay.py scripts/device_reset_control.inc gpu/race_backend.cu gpu/race_backend.h tests/driver_reset_diff.py pins.json >sources.sha256
CUDA_VISIBLE_DEVICES="$ANNS_GPU_INDEX" python3 tests/driver_reset_diff.py ./build/driver_reset_cuda cuda-evidence >cuda-report.txt 2>&1
python3 tests/driver_reset_diff.py ./build/driver_reset_probe cpu-evidence >cpu-report.txt 2>&1
cmake -S . -B sanitized-build -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer -g' >sanitizer-configure.txt 2>&1
cmake --build sanitized-build --target driver_reset_probe -j4 >sanitizer-build.txt 2>&1
python3 tests/driver_reset_diff.py ./sanitized-build/driver_reset_probe sanitizer-evidence >sanitizer-report.txt 2>&1
cat cuda-report.txt cpu-report.txt sanitizer-report.txt
REMOTE
printf 'Remote evidence: %s\n' "$remote"
