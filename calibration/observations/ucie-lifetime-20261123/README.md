# UCIe lifetime functional evidence — performance CLOSED

Final run: `cloudsys01.engr.uconn.edu:/tmp/anns-ucie.Ms5s9v`.
Runner: `ANNS_GPU_INDEX=0 bash gpu/run_ucie.sh`.
Final implementation includes RX holding-queue backpressure and ACK control-unit
ownership; earlier directories `He7Y3r` and `aMEgGi` are superseded and are not
used as evidence for the final source.

The new oracle exercises 43 transport schedules, including 300 payloads across
sequence wrap, integrity-failure injection, lost ACK, duplicate suppression,
backpressure, Retrain retention, 36 seeded reset cases, one-sided reset,
in-flight data after adapter cleanup, LinkError, and delayed ACK across reset.
Nine DeviceDriver/CSR/stage combinations feed a symbolic data token into actual
CUDA distance computation. Five compiled source mutants and one distance-output
mutant must be rejected. Expected mutant failures are deliberately saved.

The transport trace executable is CPU code in all three runs; only the final
vector-distance backend changes to CUDA in the GPU run. Sanitizer uses separately
built, fully instrumented EventLab core and probes (not a sanitized caller linked
to an uninstrumented library). `sanitizer-core-flags.txt` records those flags.

Reproduce locally:

```sh
cmake -S . -B build
cmake --build build -j4
ctest --test-dir build --output-on-failure
python3 tests/ucie_diff.py build/ucie_trace build/ucie_probe results/ucie
python3 tests/ucie_mutations.py results/ucie-mutants
```

See [clause audit and limitations](../../../docs/UCIE_LIFETIME_REVIEW.md).
These tests validate an explicitly bounded decoded-event ownership model, not a
Format-6 wire codec or complete PCIe retry/PHY state machine. A6000 has GDDR6;
there is no HBM/HBF calibration, real-corpus recall, throughput or P99 evidence.
The negative stale-byte witness in the earlier AoU suite remains a blocker for
arbitrary externally held packets outside this modeled transport boundary.

## Verified results

- Final local CTest: **26/26 passed** (`local-ctest.txt`).
- CPU, RTX A6000 GPU 0 and full-library ASan/UBSan: all new suites passed.
- **53 stdout artifacts match byte-for-byte** across the three backends.
- All recorded source hashes match the committed implementation.
- Device UUID: `GPU-9dbed927-f5be-f3cb-e181-618127b4b032`; driver 610.57.04.
  The prelaunch compute-process list was empty.
- Five compiled source mutants were rejected; their nonzero oracle exits are
  expected evidence, not failed production runs.

`comparison.json`, `device.csv`, `sources.sha256` and the per-case inputs/outputs
support these statements. The earlier upstream 500-test suite was not rerun in
this change: no pinned EventLab source or overlay was modified.
