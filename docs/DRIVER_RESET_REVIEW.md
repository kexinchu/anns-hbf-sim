# Full DeviceDriver reset integration review

Performance experiments remain disabled. This extends the pinned EventLab through
checked build-time overlays; vendor source and its pin are unchanged. It supersedes
the standalone-only scope of DEVICE_RESET_REVIEW.md **for the tested schedules**.

## What executes

`HostDriver` splits global requests through `RoundRobinInterleaver`; actual
`DeviceDriver` request serialization, bounded RX, ingress admission, WritePath
fragment assembly/deadlines, erase/program bank tickets, ReadPath/cache leases,
bounded TX, response serialization and feedback callbacks all execute. Physical
addresses come from the driver's CapacityManager, not the host page/4 domain.
Geometry is two channels, two dies/channel, one bank/die, four pages/block,
four blocks and one spare; global stripes are 64 bytes. Core service is finite
at 16 bytes/ns with 100 ps propagation; these are synthetic fixture parameters.

Reset marks affected transactions invalid but retains their cleanup ownership.
Queued callbacks and incomplete-assembly deadlines settle reservations. Program
and erase callbacks associated with invalidated writes cannot update media.
The final feedback callback rejects even a response whose serialization already
finished. Recovery deliberately waits for all old traffic to drain: this profile
does not yet model a stale external packet arriving after recovery or identifier
reuse across recovery. `DeliveredResponse.reset_invalidated` is **local simulator interruption
metadata**, not an OCP status code or new wire packet. Real electrical reset/link
retraining and bit-level packet loss are outside this model.

Pending physical blocks become unknown. Completed media remains known even when
its ACK is lost. Reads of unknown media fail without publication; recovery alone
does not clear uncertainty. Recovery resets WritePath preparation on unknown
blocks, forcing a fresh erase before ordered rewrite. A producer must explicitly
acknowledge failed content after Host drain; old failures and dependency outcomes
remain failed. This acknowledgement permits a new version, not successful replay
of an old one.

## Independent evidence and negative checks

`tests/driver_reset_diff.py` imports no simulator code. Its observable reference
contract independently predicts uncertainty and completion outcomes by cut point,
checks stage-specific live resource ownership, all 16 drain counters, and exact
handoff/acceptance/response conservation. RX/TX payload-byte reservations also
must be zero in the native probe. It computes the final 32 integer squared-L2
results from the documented token/vector formula, independently of CUDA/CPU code.

The 36 schedules are 12 cuts times warm reset, power loss and die fault:
handoff, RX arrival, partial acceptance, erase issue, program issue, program finish,
egress ready, response issue, delivered-before-feedback, sense issue, window
release and cache hit. Die read schedules additionally complete an unaffected die
and channel. Invalid channel/die, RDY writes, reserved reset type/bits and a bad
reset key are checked; premature recovery is rejected. Mutations that publish
unknown data or corrupt a distance must be caught. These are bounded directed
observable differential tests, **not an exhaustive independent implementation of
all internal scheduling or all OCP command sequences**.

CUDA consumes a concrete vector reconstructed from the successfully rewritten
physical media token using real CUDA allocations, streams and events. This is
functional transport-to-GPU evidence; it is not production ANNS vector transport,
HBM calibration, HBF hardware validation, recall or throughput evidence.

## OCP v0.7.0 clause review and residuals

Source: [official OCP HBF Architecture v0.7.0](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/).

| Clause | Implemented / checked | Remaining boundary |
|---|---|---|
| 5.9.2.3–5, EN/RDY/BUCR | Channel-local EN/RDY, reset magic, supported offsets, reserved-bit rejection, admission gate | Subset only. Driver retains donor bootstrapped initial EN/RDY=1. All reset types use a conservative common functional policy; PHY/D2D/AOU-specific retention is not implemented. |
| 7.3, reset and pending writes | In-flight fault injection taints physical pending blocks; no assumed old/new bytes; explicit drain and RDY before reuse | Host should normally drain before requested reset. Cross-stage tests intentionally inject faults outside that normal precondition. 1000 ps boot delay is synthetic; explicit recovery requires device-wide quiescence. |
| 11.5.2.7, rewrite after failure | Unknown block preparation cleared; fresh erase and ordered page-zero rewrite through the real splitter | No claim of complete replacement/retirement recovery coverage. Dynamic zone swaps and reset concurrent with replacement remain untested here. |
| 11.5.1.9 / 11.5.2.9, die recovery | Physical die-targeted invalidation; unaffected accepted die/channel reads complete | Admission is conservatively gated for the entire affected channel; recovery waits for whole-device drain. No independent die boot timing or real CSR die command is invented. |
| Power-loss interpretation | Pending writes unknown; completed media retained in this non-security profile; powered-off CSR access rejected | Cleanup callbacks advance virtual time solely for cancellation bookkeeping, not powered hardware execution. No torn-cell distribution, collateral corruption model, electrical rails or durability guarantee. |

A passing suite closes the standalone-only integration gap for these cases. It
does not certify full OCP conformance. A6000 uses GDDR6: real HBM/HBF calibration,
reset-type-specific hardware behavior, independent scheduler coverage and the
remaining mapping/replacement races are still gates before performance claims.

## Recorded result

[Raw evidence and reproduction](../calibration/observations/driver-reset-20261123/README.md):
22/22 project regressions and 500/500 modified EventLab upstream tests passed.
The 36 schedules plus 2 mutations passed on CPU, A6000 GPU 0 and a fully
ASan/UBSan-instrumented driver library; all 38 stdout traces matched exactly.
Source hashes were checked against the remote run. These results establish the
stated functional contract for these fixtures, not universal simulator correctness.
