# External reset functional validation, 2026-11-23

Performance remains disabled. This evidence applies to the source hashes recorded
here, not a calibrated HBF/HBM device. See docs/EXTERNAL_RESET_REVIEW.md for scope.

Remote isolated build: cloudsys01:/tmp/anns-external.tBQhqi. GPU 0 was checked vacant
before each CUDA suite. Device UUID and compiler/driver versions are in device.csv
and compiler.txt. Tests neither terminate nor replace other GPU jobs.

The independent suite covers 18 read-response/write-ACK cases (three reset types
and three packet arrival orders), four observable-output mutants and one reserved
reset-type negative. Native checks additionally inject stale requests, forged
response identity, duplicate packets and invalid request-generation/ID inputs.
The previous 36 cross-stage reset cases and their two mutants are regression
coverage. Every run preserves stdout, stderr, arguments and exit code.

The first upstream regression run exposed two failures: applying the delayed
external fixture's admission limit to normal traffic changed the old-ingress and
16-channel fixtures. `initial-upstream-budget-regression.txt` preserves that run.
The limit now applies only when external responses are deliberately held; normal
traffic retains the donor's budgets. `upstream-ctest.txt` is the successful rerun.
Another directed regression caught unaffected-die responses blocked by channel
readiness during die recovery; receive now preserves those accepted completions.

Reproduce from repository root:

```
cmake -S . -B build
cmake --build build -j4
ctest --test-dir build --output-on-failure
ANNS_GPU_INDEX=0 bash gpu/run_external_reset.sh
```

The remote script instruments the complete EventLab library and probes for
ASan/UBSan. Source hash equality and CPU/CUDA/sanitizer output equality must be
checked alongside reports. Output mutations are oracle self-checks, not evidence
of exhaustive implementation mutation coverage. No throughput or latency claim
follows from these functional schedules.

Final result: local 23/23 and upstream 500/500 CTests pass. All six remote suites
pass. All 23 external and 38 cross-stage stdout files match CPU/CUDA/sanitizer
byte-for-byte, including expected negative cases. Remote source hashes match
local-sources.json. GPU 0 UUID: GPU-9dbed927-f5be-f3cb-e181-618127b4b032.
