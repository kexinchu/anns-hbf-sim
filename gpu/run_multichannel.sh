#!/usr/bin/env bash
# Functional schedules only. No timing or throughput experiment.
set -euo pipefail
case "${ANNS_GPU_INDEX:-1}" in 0|1) ;; *) echo "invalid GPU index"; exit 2;; esac
archive=$(mktemp /tmp/anns-multi.XXXXXX.tgz)
trap 'rm -f "$archive"' EXIT
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='.git' --exclude='__pycache__' -czf "$archive" CMakeLists.txt pins.json src gpu/*.cu gpu/*.h gpu/*.py scripts tests vendor/EventLab vendor/HBXim
remote=$(ssh cloudsys01.engr.uconn.edu 'mktemp -d /tmp/anns-multi.XXXXXX')
scp "$archive" "cloudsys01.engr.uconn.edu:$remote/source.tgz"
ssh cloudsys01.engr.uconn.edu "bash -s -- '$remote' '${ANNS_GPU_INDEX:-1}'" <<'REMOTE'
set -euo pipefail
cd "$1"
ANNS_GPU_INDEX="$2"
case "$ANNS_GPU_INDEX" in 0|1) ;; *) echo "invalid GPU index"; exit 2;; esac
tar xzf source.tgz
cmake -S . -B build -DANNS_CUDA_VALIDATION=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc >configure.txt 2>&1
cmake --build build --target multichannel_race_cuda multichannel_race page_group_probe page_group_contract -j4 >build.txt 2>&1
gpu_uuid=$(nvidia-smi -i "${ANNS_GPU_INDEX:-1}" --query-gpu=uuid --format=csv,noheader)
nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | awk -F, -v id="$gpu_uuid" '$1 == id {print $2}' >processes.txt
test ! -s processes.txt || { echo 'Selected GPU busy'; exit 2; }
nvidia-smi -i "${ANNS_GPU_INDEX:-1}" --query-gpu=name,driver_version,uuid --format=csv >device.csv
/usr/local/cuda/bin/nvcc --version >compiler.txt
sha256sum src/multichannel_race.cpp src/page_group_probe.cpp src/page_group_contract.cpp src/eventlab_page_group.hpp src/eventlab_page_writeback.hpp src/versioned_pages.hpp gpu/race_backend.cu gpu/race_backend.h tests/multichannel_diff.py pins.json >sources.sha256
CUDA_VISIBLE_DEVICES="${ANNS_GPU_INDEX:-1}" python3 tests/multichannel_diff.py ./build/multichannel_race_cuda cuda-evidence CUDA >cuda-report.txt 2>&1
python3 tests/multichannel_diff.py ./build/multichannel_race cpu-evidence CPU >cpu-report.txt 2>&1
python3 tests/multichannel_diff.py ./build/page_group_probe mapping-evidence mapping >mapping-report.txt 2>&1
g++ -std=c++20 -fsanitize=address,undefined -fno-omit-frame-pointer -g -Ibuild/eventlab-overlay/include src/multichannel_race.cpp build/eventlab/libhbf_eventlab.a -o sanitized
python3 tests/multichannel_diff.py ./sanitized sanitizer-evidence CPU >sanitizer-report.txt 2>&1
./build/page_group_contract >contract-report.txt 2>&1
cat cuda-report.txt cpu-report.txt mapping-report.txt sanitizer-report.txt contract-report.txt
REMOTE
printf 'Remote evidence: %s\n' "$remote"
