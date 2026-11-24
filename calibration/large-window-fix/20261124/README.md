# Evidence and reproduction

This is CPU simulator correctness/execution-cost evidence, not hardware calibration or ANNS performance evidence. See `docs/LARGE_WINDOW_FIX_ZH.md` and the frozen `calibration/paper-curves/protocol-v2.json`.

- `before-*`: original device scan with host FCFS index enabled; 439.276 s wall, allowed 900 s to distinguish slow execution from deadlock.
- `after-*`, `intermediate/`: stage-only intermediate optimization.
- `final-*`: stage + prior-sense optimization before moving the CHECK-only function body out of the header.
- `release-*`: final source, including that definition-placement correction. These are the publication checks.
- `linux-*`: full-library ASan/UBSan, CHECK oracle; corresponding `release-linux-*` logs repeat this on final source.
- `subprofile*`: temporary instrumentation for hotspot attribution, not modeled device time.

Build independent reference and optimized executables from the same tree:

```sh
python3 bootstrap.py
cmake -S . -B build-scan -DCMAKE_BUILD_TYPE=Release -DANNS_DEVICE_INDEX=OFF
cmake --build build-scan --target large_window_probe -j 4
cmake -S . -B build-index -DCMAKE_BUILD_TYPE=Release -DANNS_DEVICE_INDEX=ON
cmake --build build-index -j 4
ctest --test-dir build-index --output-on-failure
python3 tests/device_index_diff.py build-scan/large_window_probe build-index/large_window_probe build-index/differential
cmake -S . -B build-check -DCMAKE_BUILD_TYPE=Release -DANNS_DEVICE_INDEX=CHECK
cmake --build build-check -j 4
ctest --test-dir build-check --output-on-failure
python3 tests/device_index_mutations.py build-check build-check/mutants
```

Large case: input lines are page IDs 0 through 1023, ascending. Invoke each executable with `4096 1024 0 0 4096`; set `PROFILE` to a distinct JSON output filename. Measure process wall time separately from the reported simulated picoseconds. Allow 900 s for the original scanner, 300 s for the optimized regression run. Host wall budgets are development-environment checks, not a universal guarantee on slower/contended hosts. Compare complete stdout and stderr, not only aggregate throughput. Four small cases additionally compare an independently built original scanner and inspect request count/IDs, times, and peak outstanding requests.

The ordered FNV64 trace fingerprint is a regression checksum, not a collision-free proof. CHECK reconstructs stage membership from the original owning transaction set and retains the original prior-sense predicate as an online oracle. Separate mechanism/reset reference tests provide additional evidence beyond two implementations agreeing.

No parameter fitting was performed. Missing paper arrival/window/raw-curve details and the service-byte versus useful-byte link-bandwidth mismatch remain open.
