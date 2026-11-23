# Full DeviceDriver functional validation, 2026-11-23

Performance disabled. Remote working directory: cloudsys01:/tmp/anns-driver.rp50J0.
GPU 0 was initially occupied; GPU 1 was authorized as an alternative but became
occupied too. The GPU 0 task subsequently exited. A fresh process check was empty
(`processes-gpu0.txt`) before this successful run on GPU 0:
NVIDIA RTX A6000, UUID GPU-9dbed927-f5be-f3cb-e181-618127b4b032.

- Local project regression: 22/22 passed (local-ctest.txt).
- Final driver probe after additional byte-reservation/stage checks: 1/1 passed.
- Modified EventLab upstream regression, experiment tests disabled: 500/500 passed.
- Remote CPU: 36 schedules and 2 mutations passed.
- A6000 CUDA: same 36 schedules and 2 mutations passed.
- Full EventLab library + probe instrumented with ASan/UBSan: same suite passed.
- All 38 stdout traces match exactly between CPU, CUDA and sanitizer builds.
- Remote `sources.sha256` matches the local sources and `local-sources.json`.

Each evidence directory preserves stdout, stderr, invocation and exit status.
Expected failed logical requests appear in stderr; the publish_unknown mutation
intentionally exits nonzero, and bad_score intentionally corrupts one distance
and is rejected by the independent Python oracle. Reports distinguish those
expected negatives from an unexpected simulator/test failure.

Reproduce from the repository root:

```
cmake -S . -B build
cmake --build build --target driver_reset_probe -j4
python3 tests/driver_reset_diff.py build/driver_reset_probe build/driver-reset-validation
ANNS_GPU_INDEX=0 bash gpu/run_driver_reset.sh
```

The remote script requires a vacant selected A6000 and does not terminate other
jobs. No HBF device, HBM timing, throughput, recall, P99 or power result is claimed.
See docs/DRIVER_RESET_REVIEW.md for OCP clauses, model assumptions and open gaps.
