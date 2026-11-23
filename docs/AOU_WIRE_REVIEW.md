# AoU HBF wire identity audit — performance gate remains CLOSED

## Primary source and decisive finding

OCP HBF v0.7.0 chapter 6 references **AoU revision 0.8, Appendix D**. The official
[OCA specification index](https://www.openchipletatlas.org/specifications/aou/0.8)
redirects to [the revision 0.8 PDF](https://cdn.sanity.io/files/jpb4ed5r/production/25de1707769f21e4a3916103371d1fb419cadac0.pdf).
Retrieved PDF SHA256: f017227aa2d0324ac8ef1ff01f8387fa93c52f00d829f2196d303a2ebdec0c25.
Appendix D is expressly a developing profile. Do not substitute a newer revision
without reviewing its compatibility with the OCP reference.

Tables 33, 41, 43 and 44 specify ReadReq, ReadData512, WriteResp and Sync. SYNC is
labelled **Time Sync**, and Sync also carries MsgCount. These tables do not define
a per-request reset epoch or a duplicate-suppression window. An 8-bit field cannot
provide the prior prototype's unbounded generation guarantee. Equal wire bytes
cannot reveal which lifetime produced them. Treating SYNC as an epoch would add
an unsupported protocol rule.

AoU 8.3.3 relies on UCIe CRC and applicable retry mechanisms for reliable message
transfer. Protocol-state errors transition to ERROR; received messages are ignored
there. Recovery is implementation-defined and returns through DISABLED and normal
activation. Chapter 8 requires both activation acknowledgements before ENABLED;
orderly deactivation waits for issued requests to complete. Section 6.4 specifies
credit-counter saturation. These are separate from application retry of uncertain
writes; OCP 7.3 does not guarantee replay safety for interrupted core writes.

## New code and what it actually proves

`aou_hbf_wire.hpp` encodes/decodes the four listed Appendix D messages as MSB-first
byte arrays. Widths, lengths, reserved zeros, split SYNC bits in WriteResp, and the
single 512-bit response's RLAST are checked. The supported ReadReq subset is one
64-byte beat with selected zero attributes. Unsupported combinations fail closed.
There is **no epoch, generation, TransferAttemptId, or CommandId envelope** in these
byte arrays or in `Link::receive(bytes)`.

`aou_link.hpp` models decoded activation control events, ERROR receive gating,
local FIFO destruction, request slots and a conservative ID-retirement policy.
It permits only a single RP and one read per live ID; it additionally refuses ID
reuse within an activation after completion, until orderly closure or error
teardown. This is a deliberately restrictive implementation policy, **not** an
AXI requirement. Closing this link is not draining the whole GPU or all channels.
Its eight request credits model request-slot capacity, not all PLP/RP credit classes.

The probe feeds decoded ReadReq into the actual EventLab DeviceDriver request,
media and response path using its trusted local submission API. Returned symbolic
media data is serialized into ReadData512. Only byte fields select the consumer
callback. The recovered response supplies real CUDA distance computation on A6000.
Internal driver IDs remain internal bookkeeping; neither external-reset prototype
API is called by this path.

SYNC and MsgCount are decoded observations, including 255-to-0 transition. No
identity, age, monotonicity or replay inference is made from them. The earlier
`try_submit_external(epoch,generation,...)` path remains a **separate historical
model**, not evidence of wire isolation or an implementation of SYNC.

## Counterexample is a retained blocker, not a successful isolation test

The fixture resets with old bytes in an owned FIFO and confirms their destruction.
It then reactivates and reuses the same ID. Under the assumed reliable lower
transport, only current bytes are delivered. Next it intentionally violates that
assumption by injecting a saved old ReadData512 after another activation reused
that ID. The AoU receiver accepts those indistinguishable bytes. The independent
oracle requires this witness to remain visible (`ambiguous_old_bytes=true`) and
requires `performance_ready=false`; hiding it is a failing oracle mutation.

Thus **arbitrary post-recovery stale injection is NOT solved** by this patch. A
complete implementation needs a verified UCIe adapter lifetime, retry-buffer and
FDI transition model, or another specification-supported closure guarantee. A
Boolean assertion that an unmodeled transport was flushed is not such evidence.
Our code clears only FIFOs it actually owns; it does not claim to flush unseen
hardware queues. Retraining, flit CRC/sequence retry, faulted partner behavior,
wire activation/credit packets and all-profile negotiation remain unimplemented.
Do not call this full OCP/AoU/UCIe conformance or hardware-calibrated recovery.

## Checks and evidence meaning

Python independently constructs Appendix D bit strings for 100 boundary/random
vectors and compares native encoded bytes; decoded fields are checked independently.
There are six malformed-byte and five out-of-range cases. Native negative checks
cover premature activation, no-credit sending, saturation, deactivation with live
requests, ID release before closure, ERROR receive/send, duplicate responses and
unsafe immediate ID reuse. Three CSR-type flows use the DeviceDriver and CUDA.
Two output mutants check detection of a bad distance and a false SYNC-isolation
claim. These are bounded contract checks, not an exhaustive second protocol engine.

No real vector corpus, ANN recall, throughput, P99, whole-system power, HBM timing
or HBF silicon behavior is measured. The payload is the documented symbolic-token
fixture, expanded into a CUDA vector. Performance experiments remain disabled.

## Recorded run

[Raw evidence and reproduction](../calibration/observations/aou-wire-20261123/README.md):
24/24 local tests pass. The new suite passes on CPU, A6000 GPU 0 and full-library
ASan/UBSan, with all nine output artifacts identical and source hashes matched.
The stale-byte counterexample remains present in every backend. Those results
validate the stated subset and the counterexample, not the missing lower transport.
