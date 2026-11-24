# Frozen v2 full-grid results (2026-11-24)

192/192 runs exited 0 and passed online plus offline per-request validation. Protocol v2 and its hash were unchanged; no fitting was performed. These are finite-batch simulator measurements, not silicon measurements or exact paper reproduction.

Primary MOCS4096, configured QD1024 (pointer effective QD1), seed8301 shown below. Both seeds and all QDs/MOCS are in `curves.csv`.

| Bytes | Cache | Pattern | Useful GB/s | P99 us | Senses | Page efficiency |
|---:|---|---|---:|---:|---:|---:|
| 256 | cold | sequential | 89.210657 | 2.938483 | 64 | 1.0 |
| 256 | cold | random | 89.210657 | 2.938483 | 1024 | 0.0625 |
| 256 | cold | pointer_chasing | 0.093987 | 2.723779 | 1024 | 0.0625 |
| 256 | hot | sequential | 1199.288142 | 0.218583 | 0 | undefined |
| 256 | hot | random | 1199.288142 | 0.218583 | 0 | undefined |
| 256 | hot | pointer_chasing | 65.996391 | 0.003879 | 0 | undefined |
| 4096 | cold | sequential | 675.393544 | 6.210163 | 1024 | 1.0 |
| 4096 | cold | random | 675.393544 | 6.210163 | 1024 | 1.0 |
| 4096 | cold | pointer_chasing | 1.476090 | 2.774899 | 1024 | 1.0 |
| 4096 | hot | sequential | 1201.715745 | 3.490263 | 0 | undefined |
| 4096 | hot | random | 1201.715745 | 3.490263 | 0 | undefined |
| 4096 | hot | pointer_chasing | 74.474081 | 0.054999 | 0 | undefined |

## What the results support

- All independent arrival windows and dependent replenishments obeyed the frozen per-request timing rule; dependency chains were invariant across ineffective configured QD.
- Cold 256B contiguous and random access consumed 64 versus 1024 senses, giving 100% versus 6.25% page efficiency. Hot runs performed zero senses, so page efficiency is undefined.
- Hot 4KiB QD1024 reached 1201.715745 GB/s, below the independently derived integer-timing service ceiling 1201.877934 GB/s. This validates consistency with the chosen byte-cost model, not the physical correctness of that byte-cost model.
- Cold 4KiB wide-window results exactly reproduced the previous macOS per-request records on Linux.

## What did NOT align

At QD1024/MOCS4096, cold 256B contiguous and random access BOTH reached 89.210657 GB/s despite different page efficiencies. The 1024-request single-wave workload activates at most one page per bank and both batches pay the initial sense delay; it does not reproduce a long streaming/page-turnover experiment. Cold 4KiB reached 675.393544 GB/s, not the paper's nominal 1536 GB/s peak. Do not omit these points, rescale their time, or claim full paper-curve alignment from the matching efficiency/dependency trends.

At low QD, hot 256B random reads outperform contiguous reads. Under the frozen 4KiB striping, the initial QD16 contiguous window touches only one channel; random seeds touch 10/11. See `initial-window-mapping.json`; this is an address-parallelism difference, not evidence of a universally faster random workload.

The published paper supplies no matching complete cold/hot/QD observations. `paper_GBps` remains blank and `relative_error_to_paper` unavailable. OCP Table 4 and §5.1.2.2 also use different aggregate values; extra model control service cost remains uncalibrated.

## Files

- `GBps.png` / `GBps.svg`: all throughput curves, two-seed min/max envelopes (not confidence intervals).
- `p99_ps.png` / `p99_ps.svg`: all per-request P99 curves.
- `curves.csv`: all 192 points including effective page utilization and unavailable external observations.
- `*.input`, `*.jsonl`, `*.stderr`, `*.status.json`: exact inputs, requests, event fingerprints, exit states and host wall time.
- `manifest.json`, `provenance.json`, `audit.json`: frozen grid, executable/source hashes and raw-artifact hashes.
- `mechanism-summary.json`: bounded qualitative comparisons; not numeric external validation.

All three gates remain false: performance_ready, hardware_calibrated, paper_curve_reproduced. ANNS performance experiments remain closed.
