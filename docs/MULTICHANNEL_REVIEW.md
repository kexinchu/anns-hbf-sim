# Multichannel page groups and joint recovery/CUDA races

Performance experiments remain closed. This is a bounded functional extension of
`WIRE_ACK_REVIEW.md`, not hardware timing calibration or full OCP conformance.

## Page splitting and aggregation

`EventLabPageGroup` accepts an aligned group containing C application pages for C
host channels, with all source pages present and D2H-complete. A group contains
C x 4096 bytes. For the configured round-robin stripe (a 64-byte multiple dividing
4096), this covers one complete local NAND page on every channel. The planner
emits every 64-byte global/channel/local mapping. The actual HostDriver splitter
performs the command submission; no alternative mock wire replaces it.

The implementation allows up to four channels in this eight-application-page
fixture. Acceptance tests cover 1, 2 and 4 channels and stripes of 64, 128, 256 and
4096 bytes. Mapping tests also exercise nonzero global base and a second group;
actual write/aggregation tests use the first local page. This is not validation of
all channel counts, port topologies or vendor address mappings.

A single 4KiB application page under small-stripe interleaving is insufficient to
fill a local NAND page. Missing neighbors, misaligned groups and incomplete D2H
are rejected; neighbors are never fabricated. The prior single-page API remains
single-channel-only. Multichannel callers use the group API, rather than bypassing
its restriction.

Owner transitions are staged and registered as one EventLab input batch. Failed
preflight or registration leaves the live owner unchanged. Each parent request ID
is unique and bound to one group. Only all terminal parent completions create a
canonical group ACK. Partial, duplicate, forged-status and stale-epoch ACKs cannot
clear dirty state. A failed aggregate retains the entire group dirty. This is a
host bookkeeping policy, **not atomic persistence or rollback of media writes**.

## Joint end-to-end schedule

One process owns the real EventLab session, four bounded GPU frames (16KiB page
storage), CUDA streams/events, page versions and completion aggregation:

1. Write a four-page prefix through EventLab, then read the old page through its
   expected-content checks and stage its concrete sidecar bytes on the GPU.
2. Submit an old-version CUDA reader behind a controlled stream gate. Refresh
   retires its frame; its lease prevents reuse.
3. Submit a complete two-channel write group. Inject one reusable program failure
   on either channel **while the actual old CUDA event is still incomplete**.
   EventLab performs its own host recovery/replay.
4. Observe partial parent completions without cleaning either group page; then
   deliver the complete group ACK. Start a second epoch and reject the old ACK.
5. Restore the next local-page group in NAND order with new payloads, read it
   through EventLab and finish a new-version GPU reader on another stream while
   the old event remains incomplete. Finally release the old reader.

The controlled gate produces a reproducible outstanding-work race. It does not
claim simultaneous execution of two kernels or predict hardware scheduling latency.
CUDA computes all 32 integer distances for each snapshot; CPU reduces ordered
top-10. An independent Python oracle computes every distance and ID, checks full
frame states at key handoffs, and checks command conservation. The expected final
832 commands/responses equal 256 setup writes + 128 reads + 384 group writes + 64
replay commands; the failed local page produces 64 error responses.

Six schedules cover three stripe sizes (64, 128, 4096) and failure on either
channel. They are directed schedules, not exhaustive interleavings. Mutations
that misbind an old ACK or reuse an old reader's frame must be rejected by the
state/result checks. A separate unit-level terminal-failure injection checks dirty
retention; it is not evidence of real permanent-failure recovery.

## OCP review

Source: [OCP HBF v0.7.0](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/), checked 2026-11-23.

| Clause | Check | Evidence boundary |
|---|---|---|
| §4.6.1 | Explicit global/local channel mapping | Independent inverse mapping; configured round-robin is a model choice. |
| §5.4.1(1–3,6) | Complete local 4KiB; non-posted responses | Complete groups, fragment counts, partial completion rejection; no packet-level certification. |
| §5.4.1(4,5,9), §11.5.2.2/6 | Local sequential writes and page-zero rewrite | Prefix restored in order; arbitrary dirty-page eviction unsupported. |
| §11.5.2.7 | Program-fail host replay | Actual reusable failure/replay with an outstanding CUDA lease; one fault per run. |
| §5.4.3 | Read/write visibility | Reads follow completed setup/restoration; pending-write read-forwarding remains covered by existing tests, not expanded here. |

Epochs, group atomic cleaning, frame pins and CUDA permits are host policy, not
additional OCP fields. Device die reset, link CRC/retransmission, persistent epochs,
uncertain remote cancellation, multiple concurrent permanent failures and power loss
remain outside this acceptance scope. EventLab still carries symbolic content;
concrete bytes are checked in the sidecar/GPU path, not serialized through AXI/UCIe.
No result here calibrates HBM/HBF latency, bandwidth, power, or production ANN scale.

## Reproduce

```
cmake -S . -B build
cmake --build build -j4
ctest --test-dir build --output-on-failure
ANNS_GPU_INDEX=0 bash gpu/run_multichannel.sh
```

The GPU script checks the selected GPU by UUID and refuses to start when busy.
Linux sanitizer checks instrument the new adapter/CPU harness; the linked EventLab
static library is not sanitizer-instrumented. CUDA evidence is recorded separately
from CPU readiness emulation. Source hashes identify the accepted code.

## Accepted results (2026-11-23)

[Raw evidence](../gpu/evidence/a6000-multichannel-20261123/) includes source
hashes, device UUIDs, compiler version, commands, exits and complete output:

- Local CTest: 19/19 passed.
- Independent mapping/aggregation: 24 positive profiles and 4 rejected inputs.
- A6000 GPU 0 (user-selected final device): 6 joint schedules and 2 detected
  mutations passed; GPU 1 independently passed the same suite before selection.
- All six positive CPU, GPU 0 and GPU 1 traces match exactly after removing the
  backend label, including frame states, command counts, distances and top-10 IDs.
- Linux ASan/UBSan adapter/harness: 6 schedules and 2 mutations passed; the
  separate terminal-failure contract test also passed.

These checks establish the directed functional contract above. They do not close
physical HBM/HBF calibration or the explicitly excluded OCP cases. Performance
experiments remain disabled.

The later [reset/cancellation review](RESET_CANCEL_REVIEW.md) adds actual permanent-program-failure tests and host drain/fence semantics. Physical reset and calibration remain open.
