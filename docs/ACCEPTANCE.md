# Acceptance gates

`performance_ready = false` until all applicable gates are reviewed with evidence.
Passing software tests does not change this flag automatically.

| Gate | Current scope | Remaining evidence |
|---|---|---|
| OCP protocol subset | 64B, 4KiB assembly, pending forwarding, overlap, credits, explicit ID group | Full ID adapter, deadline boundary ordering, faults/remap/recovery |
| Timeout | Explicit deadline drain and retry generations | Exact deadline races and host recovery policy |
| Cache | Two retained pages and same-bank issue order | Conflict/replacement/fault differential reference |
| Core Channel | Finite shared serialization, independent channels | Die ports, packet overhead, parameter provenance |
| HBM | Bounded per-PC concurrent bursts | Bank-level online commands, refresh stress, independent timing model |
| ANNS | CPU toy IVF/rerank exact output equivalence | Real GPU transfers, production ANN implementation, scale |
| Calibration | None | Hardware or bounded physical evidence, held-out error tests |
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
