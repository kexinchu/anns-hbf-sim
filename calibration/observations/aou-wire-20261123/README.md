# AoU HBF byte-path validation — 2026-11-23

Status: bounded implementation tests PASS; arbitrary stale-packet isolation OPEN;
performance_ready=false. Read docs/AOU_WIRE_REVIEW.md before using these results.

- Local regression: 24/24 CTests pass; final aou_diff rerun passes.
- Remote CPU, A6000 GPU 0 and full EventLab-library ASan/UBSan: all pass.
- Nine output artifacts match byte-for-byte across the three backends.
- Remote source hashes match the local files (local-sources.json).
- Hardware UUID and driver/compiler are in device.csv/compiler.txt.
- Remote isolated directory: cloudsys01:/tmp/anns-aou.Kb8Cs6.

The suite checks 100 independent Appendix D encoding/decoding vectors, 11
malformed/range negatives, three DeviceDriver/CUDA recovery flows and two output
mutants. Expected stale-byte ambiguity is an explicit counterexample. A passing
oracle requires the ambiguity to be reported, not concealed as isolation success.
These are not production ANNS, complete AoU/UCIe conformance, hardware link reset,
HBM/HBF timing, latency, throughput or power measurements.

Reproduction:

```
cmake -S . -B build
cmake --build build --target aou_probe -j4
python3 tests/aou_diff.py build/aou_probe build/aou-validation
ANNS_GPU_INDEX=0 bash gpu/run_aou.sh
```

The remote script checks GPU vacancy without terminating other jobs. Source
metadata, raw output, errors and invocations are retained. The official AoU 0.8
PDF was read but is not redistributed here; its URL/hash are in the review.
