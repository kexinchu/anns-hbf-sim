# Drain-before-reset, cancellation, and permanent write failures

Performance remains disabled. This extends the multichannel functional contract;
it does **not** implement physical die reset or establish full OCP conformance.

## Implementation and linearization

`EventLabPageGroup::cancel` revokes host commit permission for an active group or
an undelivered terminal ACK. It does not cancel accepted EventLab commands. All
parent responses must still arrive. After drain, the canonical failed aggregate
returns every participant to dirty-ready, including successful participants. This
preserves the complete source backup, without claiming media rollback. Cancel after
owner completion returns false; that commit has already linearized.

`reset_begin` blocks admission in the selected owner recovery domain and revokes
active/queued group ACKs. `reset_finish` refuses to resume before parent completion,
owner ACK settlement, session event drain, response conservation, and an explicit
ready indication. The conservative drain covers the whole session, even if other
scopes have work. Clean versions are invalidated; pinned old consumers retain their
frames until actual CUDA completion. Dirty backup survives for explicit ordered
page-zero replay. Request IDs are never reused; old success ACKs cannot commit the
next attempt. The existing process-lifetime token/epoch guards remain in force.

**Topology assumption:** the owner uses its existing `page / 4` recovery domains.
These are logical test domains, not a mapping of global addresses to EventLab's
physical NAND dies. The unrelated-domain test executes a cached GPU consumer;
it does not establish independent physical die throughput or transport isolation.
The explicit readiness input is a test stand-in for CSR polling, not a timer-derived
grant. EventLab exposes no public physical reset operation in this pinned version.
No power loss, register reset, PHY reset, or indeterminate-media branch is simulated.
Unsafe reset during an outstanding write is rejected, not assigned invented data.

## Actual EventLab permanent failure path

The combined driver injects `FailedUnusable` into actual program operations, rather
than fabricating terminal completions. One unusable block is replaced and replayed.
Persistent failure on either channel, or on both channels, exhausts the fixture's
one spare per bank and reaches terminal failure. The owner retains both dirty
pages and forbids eviction. Exhausted capacity is not magically repaired; the
fixture stops with failed workload status. Recovery of usable media uses an ordered
page-zero write with a new request/token/epoch on the same session.

## Independent checks and directed schedules

Nine families, each exercised with two channel-selector values (18 variants):

- Cancel before responses, after terminal response but before ACK, or after the
  first parent completion.
- Reset intent at those same three boundaries, with drain/readiness/admission checks.
- One unusable program operation followed by replacement/replay.
- Persistent unusable failures on both channels, or on the selected channel.

The selector is immaterial in non-fault families; these are not 18 distinct races.
A held real CUDA event overlaps the entire scenario, while a separate stream
completes a cached consumer in the other domain. This tests outstanding-work
lifetimes, not simultaneous kernel execution or hardware scheduling latency.

`tests/reset_diff.py` independently reduces observable owner transitions and
computes all old-reader integer distances; it imports no implementation code.
It checks command/response conservation and fixture-specific failure accounting:
64 fragments/page, original plus one spare, and two rejected recovery probes per
exhausted channel. Those probe counts are pinned EventLab behavior, not OCP rules.
Negative mutations intentionally commit a revoked ACK (cancel/reset cases) or reuse
an old leased frame; the suite must detect each corruption. Invalid reset scope,
duplicate reset, premature resume, blocked submission, unknown cancellation, and
old/duplicate ACKs are also checked in the native driver.

## Clause review and remaining gaps

Source: [OCP HBF v0.7.0](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/), inspected 2026-11-23.

| Clause | Bounded check | Not established |
|---|---|---|
| §7.3 | Drain before reset completion; pending writes cannot authorize reset | Electrical timing, actual reset, data after an unsafe reset |
| §5.9.2.5 | Kept distinct from host fencing | BUCR register/PHY/AOU/warm-reset implementation |
| §11.5.1.9, §11.5.2.9 | Block admission until explicit readiness | Real CSR polling and physical die topology |
| §11.5.2.7 | Actual program-failure replay | Arbitrary multi-page block reconstruction |
| §11.5.2.8 | Actual spare exhaustion and retained dirty backup | Persistent bad-capacity CSR discovery after power cycle |

Cancellation is a host policy, not a newly claimed OCP command. Late responses are
accounted for, never silently discarded to simulate cancellation. The bounded
sidecar/GPU data path and symbolic EventLab content remain separate; this new
fixture does not claim an end-to-end serialized media payload or production ANNS.
Neither A6000 GDDR6 execution nor these fault injections calibrate HBM/HBF timing.

## Reproduce

```
cmake -S . -B build
cmake --build build -j4
ctest --test-dir build --output-on-failure
ANNS_GPU_INDEX=0 bash gpu/run_reset.sh
```

The remote script refuses a busy device, records its UUID and source hashes, and
runs CUDA, CPU and Linux ASan/UBSan adapter/harness suites separately. The linked
EventLab static library is not sanitizer-instrumented.

## Accepted evidence (2026-11-23)

[Raw records](../gpu/evidence/a6000-reset-20261123/) preserve source hashes, GPU 0
UUID, arguments, exits and full traces. Local regression passed 20/20; after
tightening negative failure attribution, the changed test passed again. A6000
GPU 0, CPU and Linux ASan/UBSan each passed 18 positive variants and detected all
three mutations. Complete positive traces match across the three backends after
removing the backend label. These results close only the bounded contracts above;
physical die-reset implementation and calibration are still open.

The [device reset review](DEVICE_RESET_REVIEW.md) documents the new physical-media/CSR endpoint, uncertainty assumptions and remaining full-transport integration gap. Performance remains disabled.
