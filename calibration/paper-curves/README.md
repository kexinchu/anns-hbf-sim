# Frozen paper-aligned component curves

This is a component-validation workload, not permission to resume ANNS performance experiments. `protocol.json` is frozen before observing curves; its hash accompanies every run. No optimizer or fitting is performed. Paper nominal sense remains a previously fitted input, not independent evidence.

## Matched and unmatched dimensions

The [retrieval paper](https://research.ece.cornell.edu/retrieve/camera-ready/retrieve26-final50.pdf) Table II supplies 512 GiB, 16 channels, four dies/channel, 16 banks/die, two 4 KiB page buffers/bank, 4 KiB interleave and 2.72 us nominal sense. The production bank cache has exactly two slots. Global pages interleave channel first; the existing reference decoder uses bank then die. The probe independently checks the 1024-bank mapping and total capacity. Its 256 pages/block and 512 blocks/bank decomposition is an explicit assumption, not a recovered paper parameter.

The paper does not provide the full Figure 3 request trace, seed, QD grid, numeric data or exact timing boundary. Public paper/workshop lookup did not locate those artifacts. Consequently this suite is a frozen equivalent microbenchmark, **not exact Figure 3 reproduction**. Original data must be added as an independently sourced file before reporting a numerical paper error. Blank `paper_GBps` and `unavailable` errors are deliberate.

The EventLab SG2 section profile is 94 GB/s/channel (1504 total); the paper uses the OCP Table 4 value 1536. This discrepancy remains visible. Other fixed EventLab assumptions, especially ideal Core Channel and control-byte equivalents, are recorded in the protocol. They prevent interpreting a curve match as complete wire/media calibration.

## Workload and timing

Each point starts a new device with full logical 512 GiB geometry and a **4 MiB active footprint**, one page per each of 1024 banks. Capacity is symbolic, not a physical 512 GiB allocation. Initialization uses real HostDriver writes; all read results check symbolic content tokens (not physical byte payloads). A hot point reads the entire footprint before measurement. Cold points have no prior reads. These controlled states do not claim a realistic random working set or eviction/refresh characterization.

Sequential and fixed-seed permutation traces visit each page once. Reads are 256 B or 4 KiB; the latter split into 64 B wire commands. QD counts outstanding **parent requests**, not commands. Independent mode uses a completion-refilled sliding window. Chain mode releases one successor only after its predecessor's parent completion, regardless of nominal QD. This models dependency ordering, not dereferencing a data-dependent pointer on CUDA.

Time spans first measured submission to last parent logical completion. Initialization/warmup are excluded; queueing, link serialization, host splitting and assembly are included. The finite 1024-request batch includes fill/drain effects; its maximum-QD point is not a steady-state bandwidth measurement. Per-request submission/completion timestamps are retained for independent timing and QD checks.

## Fit versus validation

- The nominal sense input is fixed from Table II. No point from this sweep changes it.
- Fully utilized sequential 4 KiB steady-state throughput is reserved as a calibration condition; it must never become an independent validation claim for the same fitted sense.
- Cold/hot, small/full-page and dependency/QD curves are diagnostic holdouts from our parameter-selection process. They are **not hardware holdouts**, since no hardware target observations are available.
- Future parameter fitting must produce a new version and a training-only manifest. This protocol and its raw results remain immutable; held-out results may not select parameters. A subsequent model choice requires new untouched validation traces.

## Independent checks and limits

Exact invariants: 1024 successful parents, complete unique result IDs, cold 1024 senses/hot zero senses, parent concurrency bound, chain invariance across nominal QD, no resource leaks, and independently computed channel/bank/die mapping. Analytical lower bounds: elapsed >= one sense for cold independent reads, >= 1024 senses for cold chain; useful bandwidth <= aggregate ideal link capacity. These are loose necessary conditions, not independent predicted curves.

The two-page cache replacement policy, contention among multiple pages per bank, long-run saturation, finite Core Channel and exact Figure 3 data remain unvalidated by this footprint. They must not be inferred from a PASS here. All results keep `performance_ready=false`, `hardware_calibrated=false`, and `paper_curve_reproduced=false`.

## Reproduction

```sh
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target paper_curve_probe -j4
python3 tests/paper_curves.py build-release/paper_curve_probe results/paper-curves
```

Each directory records the protocol/source/binary hashes, input traces, raw per-request outputs, stderr, CSV curves and an explicit bounded verdict. Plot lines connect only this engine's modeled observations; no fabricated paper curve is drawn.

## Execution provenance and invalid attempts

`run-20261123` exceeded its 180-second host-wall budget during fragmented-write initialization. `release-20261123` and `burst-20261123` are explicitly INVALID: their runner referenced a build pathname that was replaced during fixture development, so a single manifest cannot attribute all their points. Their partial observations are retained but excluded from analysis. The final fixture uses supported burst writes for initialization and page-at-a-time warmup; neither phase contributes measured time. This changes preparation cost, not the frozen measurement workload.

`final-20261123` uses one unchanged production binary, checked against its initial SHA256. The original runner source is retained in that directory. Future invocations copy the executable into an exclusive result directory before running. The completion runner also freezes a binary copy, checks the original protocol/binary hashes, and attempts all missing points under the same 180-second per-point wall budget. Host timeout points remain blank, explicitly invalid, and never become low-throughput device observations. Four independent OS workers change host execution time only; this event model uses deterministic virtual timestamps.

A one-second host stack sample of the high-QD run is retained in `high-qd-host-stack.txt`. Samples concentrate in `HostDriver::pump` and candidate eligibility scanning. This suggests host scheduler execution cost; it does not prove a device bottleneck, an infinite loop, or a calibrated time prediction. No scheduler optimization is mixed into these observations. The new CTest contract rejects five malformed/out-of-grid inputs before initialization; the separate output auditor tests corrupt completion time, duplicate identity, sense count and negative latency.

If the strict runner stops on a host execution timeout, preserve its directory and complete the unchanged grid explicitly:

```sh
python3 tests/complete_paper_grid.py build-release/paper_curve_probe results/paper-curves
python3 tests/paper_curve_audit.py results/paper-curves
MPLCONFIGDIR=/tmp/anns-paper-mpl python3 scripts/plot_paper_curves.py results/paper-curves
```

The completion command refuses a changed binary or protocol. The output audit checks completed points and requires completed + explicitly invalid points to cover all 64 grid entries; this is a coverage assertion, not a claim that all 64 passed. Plots leave invalid points as NaN gaps.

## Recorded result (2026-11-23)

All 64 grid points were attempted. **56 completed and passed the independent arrival/output checks; 8 are invalid host-wall timeouts**, exclusively 4 KiB independent reads at QD 256/1024 (both orders and cache states). Therefore the high-QD 4 KiB curve and the saturation check remain incomplete. No values are imputed. The independent auditor rejected 224 corrupted output records; five invalid input cases passed the new CTest contract. These negative tests exercise the harness/output checks, not a new production fault-injection campaign.

For sequential 256 B cold reads, modeled useful bandwidth changes from 0.0940 GB/s at QD1 to 89.2107 GB/s at QD1024; hot reads reach 1199.2881 GB/s. Cold 4 KiB independent reads complete at 1.4761 GB/s (QD1) and 23.6174 GB/s (QD16), with QD256/1024 unavailable. Serial-chain results remain identical across nominal QD. These are finite-batch **model outputs**, not HBF measurements, paper observations, or validated ANNS performance.

[Raw observations and verdict](final-20261123/) · [CSV including invalid points](final-20261123/curves.csv) · [Curve plot](final-20261123/curves.png)

Remaining blockers: fix or otherwise resolve host queue-scan execution cost without altering modeled semantics (separate revision and differential checks), rerun the missing points, add steady-state and multi-page-per-bank stress profiles under new frozen versions, and obtain independently sourced paper trace/timing/numeric curve data. Fitting against the reserved throughput condition cannot validate that same condition. Physical HBM/HBF calibration remains a separate unavailable evidence layer.
