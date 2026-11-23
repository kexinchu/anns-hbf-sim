# Reset/cancel acceptance, 2026-11-23

Final acceptance uses `cuda-final`, `cpu-final`, `sanitizer-final` and
`sources-final.sha256`. The final validator requires the intended assertion text
for deliberate stale-commit failures, so arbitrary crashes cannot pass negatives.
Earlier `*-evidence` runs and `sources.sha256` are retained as preliminary records
before that validator tightening; use the final manifest for the committed tree.

GPU 0 identity is recorded in device.csv; processes-final.txt is the empty busy
check immediately before the final CUDA run. Every JSON preserves args, exit,
stdout and stderr. ctest.txt covers all 20 tests; ctest-final-targeted.txt reruns the
changed validator. Equivalence compares all positive traces across three backends.

These are host recovery-domain reset fences, not physical NAND/PHY reset. See
../../../docs/RESET_CANCEL_REVIEW.md for assumptions and remaining gaps. ASan/UBSan
instrument the adapter/harness, not the linked EventLab static library. No
performance or HBM/HBF calibration claim.
