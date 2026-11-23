# Functional evidence, 2026-11-23

- lifecycle/report-final.txt: final 25 CUDA traces plus corrupt-fill mutation.
- lifecycle/evidence: 26-JSON directory is final; 21-JSON directory is preliminary 20-trace suite before adding new-generation writeback. Final source hashes apply to the final suite only.
- anns/report.txt: five recovery cases and five negative cases, two real CUDA IVF queries each for successful cases.
- sanitizer/sanitizer-report.txt and cpu-evidence: 25 traces plus mutation, Linux g++ ASan+UBSan CPU probe; no CUDA sanitizer claim.
- invalid: initial CUDA timeout and macOS sanitizer startup failure, neither counted as pass.
- ctest.txt: final local regression results.

Device/compiler metadata and CUDA source hashes are included. GPU page state is bounded; transport faults are scripted. No physical HBF/HBM performance claim. No performance experiment resumed.
