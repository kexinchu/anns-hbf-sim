# UCIe retry ownership and reset lifetime review

**Performance CLOSED. Full OCP/AoU/UCIe conformance remains OPEN.**
This change replaces an assumed empty lower queue in a new validation path with
explicit owned queues and observable disposal. It does not turn the previous
AoU counterexample into a universal stale-packet rejection claim.

## Sources and normative boundary

OCP HBF v0.7 chapter 6 references AoU 0.8 Appendix D. AoU 0.8 section 4.1 selects
**Format 6**, not a private packet envelope or Format 2. See the
[AoU source audit](AOU_WIRE_REVIEW.md). Its introduction cites UCIe 2.0.

The reviewed UCIe source is revision 2.0, version 1.0, August 6, 2024, public
specification copy filed with the USPTO:
[PDF](https://tmng-al.uspto.gov/resting2/api/casedoc/cms/case/99231699/tmdocument/20250612064611159321SPE0012.pdf).
SHA256: `aded2d33a56b9c742ec042382fbcff1f95f4da33802d879f0100b21f6a925da0`.
The PDF is not redistributed here. Initial comparison used revision 1.1; the
following requirements and final implementation review use **2.0**.

| Clause | Requirement relevant to this change | Coverage / boundary |
|---|---|---|
| UCIe 3.8 | Eight-bit sequence counters; maximum 255; zero is not a payload sequence. Unacknowledged limit is min(buffer capacity,127). No selective NAK/RX retry buffer. | Eight-entry TX retry ownership, wrap 255→1, no RX replay store. Full PCIe-derived retry logic **missing**. |
| UCIe 3.8 | Sequence handshake on RDI Active entry from Reset/Retrain; timeout after 128 transmitted flits. | **Missing**, not replaced with a hidden epoch or Boolean conformance flag. |
| UCIe 10.2.7 | Four-phase RX-active handshake; rising response delayed at least one cycle; graceful exit closes receiver first. | Decoded request/status edges and cycle check. Full clock/wake/sideband handshake **missing**. |
| UCIe 10.3.2 | Flit-mode FDI exits stop TX at a flit boundary; RDI has stall handshake. | Transfers are atomic model units; bit/beat-level boundary and RDI stall handshake **missing**. |
| UCIe 10.3.3.5–6 | LinkReset/Disabled entry cannot wait indefinitely for retry drain; afterward clean relevant pipelines/retry state. | Entry allowed with occupied buffers; incremental disposal is observable. |
| UCIe 10.3.3.4 | Retrain has different recovery/active-entry rules. | Retry records survive Retrain. Full retrain handshake **missing**. |
| UCIe 10.3.3.7 | LinkError has exceptional entry and recovery residency requirements. | Immediate data gating; recovery deliberately unsupported, so no fictitious zero-time recovery. |
| UCIe 10.3.4.1 | Reset coordination includes remote PHY sideband completion. | Bounded pair checks both owned endpoints; actual PHY/sideband implementation **missing**. |
| OCP 7.3 | Interrupted core writes can be uncertain. | Existing device-reset model remains; transport replay does not certify application write replay. |

## Actual implementation and explicit model policies

`src/ucie_lifetime.hpp` is a **decoded-event, whole-message lifetime model**.
`Frame` contains a real-width sequence value, decoded payload/ACK kind and AoU bytes. Its `crc_ok` member is
an injected integrity outcome, not a calculated Format-6 CRC or an identity tag.
There is no epoch, request generation, transfer-attempt tag or timestamp used to
match a response. The same AoU RID can be reused after the modeled reset closure.

A full RX holding queue stalls the modeled arrival step without removing the
in-flight item. This backpressure is a simulation policy, not a claimed PHY
flow-control wire mechanism.

Each of the two endpoints owns a finite TX retry store, TX work queue and RX
holding queue; each direction has a separate finite ordered flight queue. The RX
queue holds accepted payload pending protocol consumption; it is **not** the
prohibited selective-repeat RX retry store. `send` retains bytes in the retry
store, `launch` moves a copy into physical flight, ACK control units share the owned TX and flight queues, but are not themselves
stored for replay. Delayed ACK is explicitly tested across reset; main-path
acknowledgements traverse those queues. `arrive` gates integrity and
expected sequence, `ack` releases a contiguous prefix, and explicit `replay`
reschedules retained bytes. ACK parsing, invalid ACK error classification, NAK
scheduling, implicit-sequence flits and timeout counters are not implemented.
Unexpected sequence is conservatively dropped in this bounded in-order fixture;
this is not a complete implementation of the PCIe discard/NAK rules.

Reset does not call `flight.clear()`. Already-launched bytes are stepped through
`arrive` while the receiver is closed and counted as drops. Adapter cleanup removes
one owned item per call and counts it. Reopening is refused until both endpoints
have entered LinkReset/Disabled, both RX handshakes are down, all owned adapter
queues have been explicitly emptied, and both physical-flight FIFOs are empty.
This is an intentionally restrictive **model policy**, not an assertion that
UCIe provides a software-visible queue-empty test or requires global draining.
It applies only to this single-stack pair; no other host/channel/GPU is drained.

The model assumes a finite ordered point-to-point flight FIFO, eventual stepping
of queued traffic, and no retimer or outside packet source. It has no hidden
scheduler callbacks holding packet copies. A nonresponding partner cannot be
forced to disappear: one-sided reset remains blocked. Lost ACK does not prevent
entry to LinkReset; retained records are explicitly discarded afterward.
**An actual PHY may implement the required boundary differently.** Validating
that implementation requires its sideband/training/serialization behavior.

The Active transition is a decoded event from the surrounding test environment.
It is not evidence that the unimplemented sequence-number or sideband handshake
ran successfully. No latency, bandwidth, clock rate, BER, reset duration or HBM
parameter is calibrated by these functional tests.

## Main-path integration

`src/ucie_probe.cpp` sends byte ReadReq through the modeled TX/retry/flight/RX path,
then hands decoded requests to the real EventLab DeviceDriver. Actual symbolic
media results become byte ReadData512 responses and traverse the reverse path.
Old response bytes are left at one of three stages: TX/retry, flight, or adapter
RX. All three existing CSR reset types run through these stages, followed by the
same AoU RID reused for a different address. Recovery uses the existing device
CSR implementation; this test does not redefine those CSR semantics.

The new request experiences an injected integrity failure and successful explicit
retransmission. The response ACK is delayed until after retransmission; sequence
checking prevents a second AoU callback. Only the fresh callback supplies the
symbolic vector input to real CUDA distance computation on A6000. This is a
functional DeviceDriver-to-CUDA fixture, **not a real-corpus ANN/recall result**.
It does not cover an AW/W transaction interrupted midway or arbitrary downstream
software work that produces a response after reset; prior reset tests remain
separate evidence for those implementation paths.

## Why the tests support only this scope

`tests/ucie_diff.py` constructs an independent Python payload/count ledger without
importing native implementation code. It checks expected outcomes at individual
operations, queue bounds at every step, 300 payloads across sequence wrap, retry
and lost-ACK cases, 36 seeded reset schedules with varied backlog/placement, a
one-sided reset, flight surviving both adapter cleanups, and LinkError gating.
The independent distance oracle computes 32 exact integer squared distances for
all nine DeviceDriver/CSR/stage combinations.

`tests/ucie_mutations.py` recompiles **production source** with five faults:
receiver gate removed, duplicate suppression removed, flight fence removed,
same-cycle handshake accepted, and cleanup incorrectly allowed in Retrain.
Each mutant must fail the independent ledger. These are stronger than merely
changing a final success flag, but are still bounded tests, not exhaustive proof.
A separate output mutant checks the distance oracle. Raw inputs, outputs, statuses
and source hashes are retained with the run evidence.

## Remaining blockers and reviewer conclusion

The modeled queues now provide evidence of where old bytes go; queue emptiness
is measured from operations instead of asserted by a test helper. Within that
closed ownership scope, the tests exercise a reset boundary without extra wire
identity. **This does not close full real-link isolation.**

Remaining work includes Format-6 packing and calculated CRC; the PCIe-derived
ACK/NAK/implicit sequence/timeout machine; RDI sequence handshake; full FDI/RDI
sideband, stall and training state transitions; optional retimer ownership;
multiple stacks; and byte/beat-level partial-frame assembly. Unsupported scenarios
must remain open until independently tested. A saved byte-identical packet
injected from outside the modeled ownership boundary after reopening remains
indistinguishable; the earlier AoU negative witness is retained unchanged.

Do not claim silicon equivalence, OCP certification, arbitrary stale-byte
rejection or performance validity from this commit. A6000 is GDDR6 and validates
CUDA function only; HBM/HBF calibration and performance authorization stay closed.

## Recorded validation

[Raw evidence and reproduction](../calibration/observations/ucie-lifetime-20261123/README.md):
26/26 local CTest; 43 transport schedules and nine main-path flows passed on CPU,
idle A6000 GPU 0 and full-library ASan/UBSan. All 53 stdout artifacts match;
source hashes match. Five compiled source mutants were detected. These results
support the bounded model described above, not the remaining conformance claims.
