# EventLab page transport and writeback identity review

Performance remains disabled. This extends the bounded functional milestone;
it does not establish physical HBF/HBM fidelity or complete OCP compliance.

## Implemented path

`VersionedPages` creates a unique 64-bit write token and a per-page monotonically
increasing epoch for every accepted attempt. ACK matching includes page, token,
epoch and the saved frame generation. Stale success **and failure** leave the
current writeback unchanged. Successful matching completion alone clears dirty;
failed completion keeps data dirty. Counter exhaustion fails closed. Identities
are process-lifetime metadata, not persistent across restart.

`EventLabPageWriteback` maps an immutable GlobalRequest ID to that identity.
It requires D2H completion before registration and binds the terminal
GlobalCompletion to the original identity. Registration exceptions roll back the
page to dirty-ready. IDs cannot be reused. This bridge explicitly rejects multi-host-channel configurations: a globally contiguous 4KiB request need not be one complete local NAND page after interleaving. Duplicate/unknown/nonterminal transport
completions are rejected. Delayed ACK delivery is independent of transport progress.

The ANNS main source now uses the same page owner. EventLab read completion,
HBM staging, publication, consumer lease and eviction form one causal path.
With `ANNS_CUDA_VALIDATION=ON`, two real GPU frames execute H2D, integer distances
and D2H under CUDA events. Query top-k reduction in this integrated driver remains
on CPU. CUDA event synchronization gates publication/reclamation; modeled HBM
latency is never a substitute for device completion. GPU wall time is deliberately
not used to infer simulator timing or throughput.

The `wire_writeback` mode rewrites the fixture's entire eight-page prefix in order,
using a new content identity. Each page is copied back from the GPU, checked byte
for byte, submitted through EventLab, and evicted only after its matching terminal
ACK. This is not a random-write cache or production block-remapping manager.

**Meaning of wire integration:** this uses EventLab's existing
SimulationSession -> HostDriver -> command splitter -> DeviceDriver -> response
and recovery path. It is decoded command/response integration, not serialized
AXI/UCIe packets, a PHY, or a network transport. EventLab carries symbolic content
tokens; concrete vector bytes remain in the explicitly checked sidecar/GPU path.

## OCP clause review

Primary source: [OCP HBF v0.7.0](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/), accessed 2026-11-23.

| Clause | Requirement checked | Evidence / remaining boundary |
|---|---|---|
| §5.4.1(1–2) | Non-posted completion after programming; one response per command | 4KiB splits into 64 commands/responses; dirty persists until terminal ACK delivery. No packet-level electrical claim. |
| §5.4.1(6), §11.5.2.5 | Complete-page assembly and timeout handling | Existing deadline tests retained; bridge submits whole pages. No new partial CUDA-page assembly claim. |
| §11.5.2.2, §11.5.2.6 | NAND rewrite/order restrictions | Main path rewrites ordered prefix; repeated page-zero rewrites use new content IDs. Arbitrary dirty eviction is unsupported. |
| §11.5.2.7 | Program-fail replay | One injected reusable failure; independent accounting checks 64 failed responses and 64 replay commands before success. Broader faults retain existing recovery tests. |
| §5.2.4, Table 13 | Command identity and status | Existing EventLab ID/status matching retained. Host token/epoch is additional internal metadata, not a new OCP field or permission to discard legal device responses. |

## Independent and negative evidence

- Lifecycle Python oracle: 30 traces (six families x five payload/interleaving
  variants), including old token, wrong epoch, wrong page, pending valid ACK,
  duplicate ACK, and ACK after frame reuse. The original corruption mutation
  must still fail the integer-distance oracle.
- Wire oracle: 16 bounded traces, eight clean and eight with a real EventLab
  reusable program failure. It compares manually specified page transitions and
  independent fragment/response/replay counts after each action. ID changes are
  variants, not 16 distinct failure modes. A deliberately misbound old ACK must
  fail this oracle.
- Integrated ANNS: independent Python IVF top-10 answers for both queries; clean
  and ordered writeback runs; wrong-address, corrupt-payload and early-consumption
  mutations must fail. Internal native distance checks cover every CUDA score.
- CPU and CUDA evidence are labeled separately. Passing CPU probes is not GPU
  evidence. Source hashes and raw traces accompany the accepted CUDA runs.

## Open boundaries

No cross-restart epoch persistence, cancel/timeout protocol for uncertain remote
commits, full NAND-block dirty eviction policy, serialized link errors, real ECC,
or hardware HBF/HBM calibration is implemented here. GPU stream operations in the
integrated ANNS driver are synchronous at handoff; controlled concurrent races are
covered by the separate lifecycle driver. EventLab failure injection and actual
CUDA races are tested separately, not yet a combined asynchronous fault campaign.
The old lifecycle acceptance document remains historical; its missing-token and
missing-EventLab statements are superseded by this document's bounded scope.

## Accepted run and reproduction (2026-11-23)

- Local CTest: **16/16 passed**.
- A6000 controlled lifecycle: **30 traces passed**, corrupt-fill mutation rejected.
- A6000 EventLab integration: native IVF equivalence, **8 ordered writebacks**, and
  **3 negative cases passed**, in a fresh remote build via `gpu/run_eventlab_cuda.sh`.
- EventLab ACK differential: **16 traces passed**, misbound-ACK mutation rejected.
- Linux ASan+UBSan: lifecycle and wire-adapter probes passed their respective
  differential suites. The prebuilt EventLab library itself was not sanitizer
  instrumented in the adapter run; this is not whole-backend sanitizer coverage.

Artifacts: [`gpu/evidence/a6000-wire-20261123`](../gpu/evidence/a6000-wire-20261123).
Source hashes are verified against the checkout before commit. Byte counters in
ANNS's final summary describe the original read/compute phase; the additional
post-query writeback validation is reported separately as eight 4KiB writes.

```
cmake -S . -B build
cmake --build build -j4
ctest --test-dir build --output-on-failure
bash gpu/run_lifecycle.sh
bash gpu/run_eventlab_cuda.sh
```

Initial development uncovered a missing registration rollback on duplicate content
and an oracle expectation of `busy` where writeback eviction returns `unavailable`.
An additional contract run exposed the default multi-channel profile mismatch; a single-channel contract and explicit multi-channel rejection now cover it. The bridge restores dirty-ready on registration exceptions; the oracle retains
the documented API distinction. No failed development run is counted as acceptance.
