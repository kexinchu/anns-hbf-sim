#!/usr/bin/env bash
# Run on the selected host; pass the uploaded probe source. No device reconfiguration.
set -euo pipefail
run_dir=$(mktemp -d /tmp/anns-a6000-observe.XXXXXX)
cp "$1" "$run_dir/probe.cu"
nvcc -O2 -std=c++14 -arch=sm_86 "$run_dir/probe.cu" -o "$run_dir/probe" >"$run_dir/build.log" 2>&1
nvidia-smi -i 1 --query-compute-apps=pid --format=csv,noheader >"$run_dir/processes.txt"
if test -s "$run_dir/processes.txt"; then echo "GPU busy; no probe launched: $run_dir"; exit 2; fi
nvidia-smi -i 1 --query-gpu=name,driver_version,clocks.current.graphics,clocks.current.memory,ecc.mode.current --format=csv >"$run_dir/device-before.csv"
nvcc --version >"$run_dir/compiler.txt"
(cd "$run_dir" && sha256sum probe.cu >source.sha256)
set +e
CUDA_VISIBLE_DEVICES=1 "$run_dir/probe" >"$run_dir/results.jsonl" 2>"$run_dir/stderr.log"
rc=$?
echo "$rc" >"$run_dir/exit-status.txt"
nvidia-smi -i 1 --query-gpu=name,driver_version,clocks.current.graphics,clocks.current.memory,ecc.mode.current --format=csv >"$run_dir/device-after.csv"
echo "$run_dir"
cat "$run_dir/exit-status.txt" "$run_dir/results.jsonl" "$run_dir/stderr.log"
exit "$rc"
