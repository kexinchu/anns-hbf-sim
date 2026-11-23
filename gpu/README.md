# A6000 ANNS and recovery functional loop

This fixture runs real CUDA distance and top-k kernels on cloudsys01 GPU 1.
It reuses the simulator's deterministic 256x32 integer dataset, four IVF lists,
two probed lists and two queries. Coarse-list selection runs on the CPU; all 128
candidate distances and top-10 selection run on CUDA. This is deliberately a
functional fixture, not a competitive ANN implementation or throughput benchmark.

The byte-backed HBF test transport injects OCP-style responses into ReadRecovery
before publishing page data. UECC corrupts stored bytes, blocks delivery, restores
all eight pages from a host backup, verifies each page and rereads before H2D.
CECC follows the same eager refresh policy while preserving valid data semantics.
Retry carries stage 3; die recovery blocks same-die reads/writes, permits an
independent die, and waits for a ready poll. Kernel results cannot precede H2D
completion; default CUDA stream ordering and synchronization enforce dependencies.

Run from repo root: `bash gpu/run_cloudsys01.sh`. It uses CUDA 12.9 and checks GPU1
for compute processes immediately before execution. This snapshot is not an
exclusive GPU reservation. It does not change ECC/clocks or launch ANN benchmarks.

## Recorded verification

`evidence/a6000-20261123/` contains stdout, error/exit outcomes, source SHA256,
compiler/device information, the simulator trace and a comparison record.
Five valid cases (clean/retry/cecc/uecc/die) match independently generated Python
candidate IDs, every integer distance and top-k. All five top-k outputs also
match `anns_loop_bank`. Five negative cases check refresh failure, absent backup,
wrong retry stage, premature publication guard, and actual corrupted GPU input.
The early-publication case exercises a guard, not an out-of-order CUDA execution.
The corrupted-input case exits normally in CUDA but is rejected by the independent
reference: program exit success alone is never the acceptance criterion.

## Evidence limits

The transport is an in-process byte array with scripted faults. It is NOT the
EventLab AXI/ARuser codec or real HBF hardware. Refresh acknowledgements here
follow actual byte writes and readback, but not timed NAND erase/program commands.
The backup is a trusted CPU copy; no durable journal or power-loss test exists.
Faults occur on the first read, sequentially, with no asynchronous in-flight
retirement races. The die topology is the small policy test geometry.

Thus the GPU and recovery policy are now connected in one functional data path;
full EventLab wire-level recovery and concurrent fault coverage remain open.
No HBF timing, GPU scheduling fidelity, HBM calibration, production recall or
performance conclusion follows from these results. `performance_ready=false`.
