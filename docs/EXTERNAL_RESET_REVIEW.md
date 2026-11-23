# External packets, ID reuse and reset domains

Performance remains disabled. This review extends DRIVER_RESET_REVIEW.md; the
previous fully drained recovery limitation no longer applies to external packets
or unrelated channels. Local aborted pipeline ownership still must be reclaimed
before that channel's internal command slots are reused.

## Executed path and ownership

Normal EventLab response serialization, TX release and feedback now detach a
response into an outstanding transport record. The default delivers immediately;
the fault fixture can hold and extract a packet value, delay it across reset,
repeat it, or inject it while a newer request uses the same command/AXI ID.
Receive requires channel, command, response kind, link epoch and unique transfer
attempt to match a live record. Rejection cannot complete or free a newer request.
Successfully delivered and cancelled records are removed exactly once.

External **requests** enter `try_submit_external` before the ordinary DeviceDriver
RX/link/assembly/bank path. An old epoch or already-seen request generation is
rejected before RX reservation, media changes or duplicate-live-ID lookup.
Watermarks advance only for Taken requests; backpressure does not consume a
request generation. New requests can reuse command ID 42 and AXI ID 42; the old
request and response copies remain injectable both across reset and within the
same connection. HostDriver's existing trusted local entry remains available.

Epoch, request generation and transfer attempt are **simulator adapter metadata**,
not additional OCP packet fields and not a model of the wire SYNC encoding. An
actual transport would need a demonstrated equivalent identification/quarantine
mechanism. No cryptographic authenticity or corrupted-payload detection is claimed.
The external fixture restricts command and AXI IDs to a 14-bit namespace and uses
nonzero monotonic 64-bit generations. The internal CommandId type remains wider.
Watermark history is bounded by channels × 16384 IDs; it is not one record per
request. A delayed-response fixture admission budget bounds active/held records;
packet copies explicitly extracted by the test are owned by its bounded fault
schedule. This fixture budget does not replace the donor's normal RX/TX budgets.

Recovery now checks the affected channel's internal transactions and its synthetic
boot deadline, not `DeviceActivity::drained()`. Tests require recovery while
another channel is actively sensing and old packet copies remain outstanding.
Physical-die fault isolation preserves already accepted unaffected die responses.

## Normative requirements versus chosen functional profile

Source: [OCP HBF v0.7.0](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/),
5.9.2.3–5 and 7.3 (pages 72–73 and 82).

The specification names the three BUCR scopes, its reset key and reserved type,
and defines EN/RDY. It requires the host to complete ongoing transactions before
requested reset and warns that interrupted core writes are nondeterministic.
Thus our in-flight fault tests deliberately go beyond the normal host precondition;
the following retention/replay choices are not normative guarantees.

| Type | Specified scope | Executable model choice |
|---|---|---|
| 00 | PHY + D2D | Advance connection epoch; retain EN and completed AoU response records. Reissue retained records with a **new** epoch after recovery. Original packets stay stale. |
| 01 | PHY + D2D + AoU | Advance connection and AoU generations; retain EN; fail pending external response records once rather than reissue them. |
| 10 | Channel warm reset | Advance connection/AoU/warm generations; clear EN; fail pending external records; require explicit re-enable. |
| 11 | Reserved | Reject without executing reset. |

All three lower RDY. Pending internal writes conservatively become unknown and
follow the existing cancelled-write cleanup policy; **type 00 does not promise
transparent replay of partially assembled or in-flight core commands**. The
implemented AoU state is its completed-response record set, not a complete AoU
RTL state machine. Completed media retention, EN retention for 00/01 and the
1000 ps recovery delay are explicit model choices. No electrical reset pulse,
link retraining timing, security erase or vendor-specific retention is simulated.
The specification's register-map summary and detailed BUCR access labels differ;
this implementation follows the detailed write-trigger description, not the
summary's read-only label.

## Independent and negative checks

The Python reference imports no simulator code. It predicts type-specific scope,
EN/RDY, old completion outcome, exactly-once callback counts, nonquiescent recovery,
no stale publication, final resource drainage and the 32 integer squared-L2 scores.
Read data has an independent global-to-local stripe/token calculation; write ACK
cases consume the newly programmed physical media token on CUDA.

There are 18 schedules: read response/write ACK × 3 reset types × 3 arrival orders.
Native checks cover reset-disabled admission, live-ID duplication, old request
arrival before and after newer completion, same-epoch request/response reuse,
forged old epoch with a new attempt, wrong channel/command, duplicate delivery,
zero request generation and out-of-range external identity. Four explicit observable-output mutants
(stale request acceptance, stale response acceptance, callback alias and corrupted
distance) must fail the independent oracle; reserved reset type must fail natively.
The 36 previous cross-stage schedules also remain regression tests.

This is a bounded observable differential reference, not a second full scheduler
or exhaustive protocol model. Reset overlapping dynamic remapping/replacement,
generation exhaustion, adversarial payload corruption and vendor-specific reset
state are not certified. A6000 supplies real CUDA execution on GDDR6, not HBM/HBF
calibration. Correctness evidence here does not reopen performance experiments.

## Verified evidence

[Evidence and reproduction](../calibration/observations/external-reset-20261123/README.md):
23/23 project CTests and 500/500 modified upstream CTests passed. Final CPU,
A6000 GPU 0 (UUID GPU-9dbed927-f5be-f3cb-e181-618127b4b032), and full-library
ASan/UBSan runs passed both suites. The 23 new stdout traces (18 schedules, four
oracle mutations, one reserved-type rejection) and 38 previous cross-stage traces
match byte-for-byte across all three backends. Remote source hashes match the
committed sources. This proves the listed bounded functional observations, not
full OCP conformance or a physically calibrated simulator.
