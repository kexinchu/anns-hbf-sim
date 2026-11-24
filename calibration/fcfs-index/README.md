# FCFS host-execution optimization — 2026-11-23

The final `terminal-replay-20261123` run completes **64/64** frozen points.
**56/56** previously completed outputs are byte-identical, including every
request's submit/completion timestamps. The eight previous host timeouts now
complete; the longest final point takes 102.68 host seconds under the unchanged
180-second limit. No model parameter or arrival trace was tuned.

The paired local Release execution test (`paired-wall-20261123`) uses identical
compiler/flags and ABBA/BAAB order, four repetitions per binary. For the fixed
4-KiB cold sequential QD=16 fixture, median wall time is **4.851 s → 2.873 s**
(**1.689×** host execution speedup). Every repetition matches the old virtual
trace. This is one fixture, not a general speedup bound and not device latency.

Validation:
- ON and CHECK: 34/34 CTest groups each.
- Four pinned donor Host suites: 113 named scenarios, plus two new race cases.
- Five production mutations rejected; 256 corrupt output records rejected.
- Full-library Linux ASan+UBSan, O1 CHECK: six Host groups passed, 31.65 s.
- Local UBSan: six Host groups passed. Local ASan is an infrastructure failure
  even on empty main; its logs are preserved. Linux O0 CHECK hit the unchanged
  60-second per-scenario limit on `sixteen_channels`; O1 rerun passed.

`replay-20261123`, `cursor-replay-20261123`, and `guard-replay-20261123` are
incomplete intermediate attempts, with immutable binary hashes, overlay source
snapshots and timeout logs. They are not substituted for the final run. Raw
executables remain ignored; source and SHA256 provenance are versioned.

See [implementation review](../../docs/FCFS_EXECUTION_REVIEW.md),
[summary](summary.json), [curve data](terminal-replay-20261123/curves.csv),
[model-only plot](terminal-replay-20261123/curves.png), and
[independent audit](terminal-replay-20261123/independent-audit.json).

**Performance gate remains closed.** This establishes execution equivalence and
completes the finite component sweep. It does not establish OCP certification,
HAVEN curve reproduction, steady-state saturation, or HBM/HBF hardware calibration.
