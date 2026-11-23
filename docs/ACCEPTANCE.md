# Acceptance gates

`performance_ready = false` until all applicable gates are reviewed with evidence.
Passing software tests does not change this flag automatically.

| Gate | Current scope | Remaining evidence |
|---|---|---|
| OCP protocol subset | 64B, 4KiB assembly, pending forwarding, overlap, credits, explicit ID group | Full ID adapter, broader faults/remap/recovery |
| Timeout | Explicit deadline drain and retry generations | Selected same-tick policy now tested; broader interleavings and autonomous host recovery remain |
| Cache | Two retained pages and same-bank issue order | Conflict/replacement/fault differential reference |
| Core Channel | Finite shared serialization, independent channels | Die ports, packet overhead, parameter provenance |
| HBM | Bounded per-PC bursts; synthetic bank backend integrated into CPU ANNS fixture | Refresh/bank-group fidelity, actual GPU integration and hardware timing still pending |
| ANNS | CPU toy IVF and real A6000 CUDA candidate-distance/top-k equivalence, with scripted recovery | Decoded EventLab + CUDA page path now tested; combined asynchronous wire/GPU faults, production ANN implementation, scale |
| Calibration | A6000 GDDR6 dependent-load observations only; no fitted model | HBM evidence, parameter fit and held-out error tests |
| Performance | CLOSED | Arrival protocol, recall/resource budget, P99 and cache state frozen |

Protocol assertions refer to OCP v0.7 §5.3.1, §5.4.1(6), §5.4.3,
Tables 12/13 and §5.9.2. Timing assumptions are separate from normative rules.
The explicit timeout test checks terminal state, not precise deadline latency.
Same answers do not establish full-library recall or memory residency.
Do not publish QPS/P99, power, or HBF superiority from this validation scaffold.

Reviewer requirements: preserve unmatched commands and raw traces; distinguish
upstream self-tests from independent oracles; report unsupported scenarios as
unsupported; publish configuration and pinned code; keep calibration data separate
from evaluation. Similar predictions from related simulators are not independent
hardware validation. No blanket conservative-bound claim is supported.

See [new recovery/deadline/bank evidence](RECOVERY_BANK_REVIEW.md). New candidate tests do not change the performance gate.

See [A6000 functional recovery evidence](../gpu/README.md). CUDA execution does not change the calibration or performance gate.

See [writeback identity and EventLab integration review](WIRE_ACK_REVIEW.md). The performance gate remains CLOSED.

See [multichannel aggregation and joint race review](MULTICHANNEL_REVIEW.md). Directed reusable program-fail/CUDA races supplement, but do not exhaust, asynchronous fault coverage.
