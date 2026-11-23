# Versioned CUDA page lifecycle: functional acceptance

Performance experiments remain **disabled**. This change tests a bounded host page
policy and real CUDA visibility/lifetime operations; it is not HBF hardware
calibration, HBM timing validation, or complete OCP conformance.

## Design and provenance

Conceptual inspiration: SlugLab's page directory and bounded HBM cache, at the
revision pinned in `pins.json`. This implementation is original; vendor code is
unchanged. `VersionedPages` owns two frames, page generations, in-flight fills,
consumer pins, dirty state and die admission gates. The CUDA adapter alone supplies
actual event readiness. Simulated elapsed time cannot grant a consumer permit.

A refresh advances the page generation. An older fill retains its frame until its
H2D event completes, then is discarded. A previously admitted reader may finish
its captured version; new readers require the current published generation. This
is **per-lease snapshot semantics**, not an atomic snapshot across an entire query.
A retired frame cannot be reused until the last consuming CUDA event completes.
Dirty or writing pages reject refresh. A failed writeback retains dirty data and
prevents eviction; successful retry clears dirty state. Die isolation rejects new
admissions but drains previously admitted operations. It does not cancel CUDA work.

`gpu/anns_recovery.cu` now scores each selected page through this owner, with H2D
publication and consumer-completion events before frame reuse. The existing
256-vector, two-query IVF2/4 fixture still checks all 128 candidate distances per
query and ordered top-10. Its host transport remains scripted. The ANNS driver is
serial across pages; concurrent races are exercised by the lifecycle driver.

## Independent checks

`gpu/verify_lifecycle.py` produces expected state without importing C++ code:
page IDs, generations, frame state, pin counts, dirty state, all 32 integer L2
scores and ordered top-10 for every completed read. Writeback checks include the
backing page's first and last words (not a whole-page persistence checksum).

Five scenario families each use five seeded payload/interleaving variants:

| Scenario | Required observation |
|---|---|
| Late old fill | Pending before event; stale after refresh; new data unchanged |
| Refresh with reader | Old snapshot preserved; third fill rejected while full; frame released only after reader |
| Failed writeback | Pending commit, failed commit, dirty eviction rejection, retained read, successful retry |
| New-generation writeback | New ready frame selected while old retired frame is pinned |
| Die isolation | New reads/refresh/writes blocked on one die; other die completes; accepted old read drains |

These are 25 bounded traces, not 25 distinct failure classes or exhaustive
interleaving exploration. Duplicate publish/release and early visibility are
rejected. A real input-byte corruption mutation must fail the independent distance
oracle. Host-only tests use simulated event readiness; only the CUDA run demonstrates
actual event visibility. A6000 uses GDDR6 and supplies no HBM/HBF timing evidence.

## Reproduction and evidence

From repository root:

```
cmake -S . -B build
cmake --build build -j4
ctest --test-dir build --output-on-failure
bash gpu/run_lifecycle.sh
bash gpu/run_cloudsys01.sh
```

Both remote scripts check GPU 1 by UUID before launch, leave other processes alone,
and retain compiler/device metadata and source SHA256s. The compute-process query
on this host returned processes outside the selected GPU; filtering by UUID fixes
the previous false busy indication. This is a check, not an exclusive GPU reservation.

Controlled streams use host gates to force incomplete events. All allocations and
kernel warmup happen before gates: the initial CUDA run timed out because first-use
kernel loading could synchronize with a held stream. That invalid run is retained.
macOS ASan failed during sanitizer initialization; Linux ASan+UBSan is the relevant
sanitizer result, with raw output retained.

## Remaining review boundaries

- Page versions, cache policy and die admission are host model assumptions, not
  new OCP requirements. Existing OCP protocol tests remain separate; no OCP gap is
  closed solely by these CUDA tests.
- Writebacks are serialized per page with a local event. There is no independent
  transport writeback token/epoch, so delayed remote acknowledgements across retries
  are not supported or validated. No power-failure persistence claim is made.
- Finite GPU page storage is 2 x 4096 bytes. Query/results and the lifecycle driver's
  fixed 64-entry stream/event/output pool consume additional memory. This is not an
  8192-byte whole-program GPU memory claim or a production cache implementation.
- Faults are injected in scripted transport; no physical ECC decoder, vendor read
  retry, refresh media behavior, or die reset timing is calibrated.
- Real GPU events do not connect this path to EventLab wire traffic or validate
  HBM bank scheduling on hardware. Those integration/calibration gates stay open.

## Observed acceptance results (2026-11-23)

- Local CTest: **13/13 passed**.
- cloudsys01 GPU 1, RTX A6000: **25/25 lifecycle traces passed**; corrupted H2D
  input rejected by the distance oracle.
- Updated CUDA ANNS path: **5 recovery cases + 5 negative cases passed**.
- Linux g++ ASan+UBSan CPU lifecycle probe: **25/25 traces passed**, mutation rejected.
- CUDA source hashes were checked against the local files before commit.

Raw evidence: [`gpu/evidence/a6000-lifecycle-20261123`](../gpu/evidence/a6000-lifecycle-20261123).
This passes the bounded functional milestone above, not the remaining calibration
or integration gates. GitHub Actions results are separate from these local/remote runs.
