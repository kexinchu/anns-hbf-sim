# Host execution optimization: evidence and semantic boundary

This change accelerates execution of the simulator on the host CPU. It does not
change simulated bandwidth, latency, topology, mapping, cache capacity, fault
policy or arrival protocol. It is not an HBF/ANNS speedup claim and does not open
the performance gate.

## Why these changes are semantically narrow

- Built-in FCFS keeps a secondary index ordered by `(enqueue_sequence, unit_id)`.
  Eligibility is evaluated live, including dependencies, retry state and open
  DLUs. Custom policies still receive the original complete candidate vector.
- A cursor skips the already traversed prefix after NotTaken within one pump.
  The public port contract forbids inline callbacks. A successful handoff resets
  the cursor: it can unlock an older grouped read. Requests rejected earlier in
  this pump remain in the original `tried` set. Command allocation and every
  `try_submit` call retain their original position; no ingress-capacity shortcut
  assumes that all addresses have identical admission behavior.
- With the monotonic failed-parent count equal to zero, no read dependency can
  be failed. Only that vacuous scan is skipped. CHECK builds retain the old scan.
- Reclamation indexes terminal units, in the original map-ID order. All retry,
  recovery, pending-result and reference checks remain at the same callback
  boundary. Requeue removes the terminal entry; actual reclamation removes it.

`ANNS_FCFS_INDEX=OFF` preserves the previous overlay. `ON` enables optimization;
`CHECK` additionally reconstructs complete queue/terminal memberships and compares
FCFS choices with the original full scan at every decision. This oracle shares
eligibility logic with production: it validates the optimization, not the
physical timing model. The Python curve audit independently checks output,
arrival-window and simple bound invariants, not physical timing either.

## Deliberate rejection tests

Production mutation tests remove cursor reset, reverse age order, omit handoff
cleanup, omit terminal completion indexing, and omit requeue cleanup. Each must
fail with an index/selection diagnostic, not an arbitrary crash or timeout.
A dedicated online PendingDluLimit retry checks that a refused fragment retries
once, valid fragments do not replay, and temporary Host state is reclaimed.
The cursor race makes an older grouped read eligible after a successful bypass.

## External validation remains separate

The frozen 512-GiB profile, finite 1024-request traces and timing boundaries are
unchanged from `calibration/paper-curves/protocol.json`. Byte equality against
previously completed traces is a regression check. Previously timed-out points
have no original completed time trace to compare against. Completing them is
coverage, not proof that OCP/HAVEN timing is correct. No HBM device calibration,
raw HAVEN reference curve, or independent device timing oracle is supplied by
this change. A6000/GPU tests are outside this host-only optimization.

Raw attempts and their source/binary hashes are retained in
`calibration/fcfs-index/`. Wall times collected during other builds/runs are
execution diagnostics, not controlled speedup measurements. Earlier timeouts
remain visible; no timeout is assigned a simulated throughput.

## Reproduction

```sh
python3 bootstrap.py
cmake -S . -B build-check -DCMAKE_BUILD_TYPE=Release -DANNS_FCFS_INDEX=CHECK
cmake --build build-check -j4
ctest --test-dir build-check --output-on-failure
python3 tests/fcfs_mutations.py build-check /tmp/fresh-fcfs-mutants
cmake -S . -B build-fast -DCMAKE_BUILD_TYPE=Release -DANNS_FCFS_INDEX=ON
cmake --build build-fast --target paper_curve_probe -j4
python3 tests/fcfs_curve_replay.py build-fast/paper_curve_probe /tmp/fresh-fcfs-curves
python3 tests/paper_curve_audit.py /tmp/fresh-fcfs-curves
```

Use new output directories. The replay retains an immutable executable copy and
source hashes. Run ON for the full high-QD diagnostic grid: CHECK deliberately
restores exhaustive decision checks and is not an execution-speed configuration.

Local Apple Clang 15 ASan could not initialize even for an empty `main`. Its
initial link failure (new libc++ deque annotation symbol) and runtime failure are
retained as invalid infrastructure attempts. Disabling libc++ ASan annotations
fixed only linking, not initialization; it is not a substitute for an ASan pass.
Linux validation uses the unmodified ASan/UBSan instrumentation of the full
EventLab library and Host test executables. No GPU is allocated by these tests.

## Cost and limits

The age and terminal sets add O(resident units) host metadata and O(log N) update
work. This trades host memory for fewer full scans; it is not a claim of lower
modeled GPU/HBF memory usage. Runtime profiling counters for queue/reclamation
visits intentionally change; request IDs, callback boundaries, attempt identity,
responses and virtual times must not. Finite workloads retain terminal metadata
until Host destruction, consistent with their existing no-reclaim diagnostics.
The remaining high-QD cost includes real `try_submit` rejection attempts and
wait-registry work; removing these requires a separate semantic proof, especially
for address-dependent backpressure and injected command-ID faults.

For a controlled local wall-time comparison, first finish other local validation
jobs, build the same source with `ANNS_FCFS_INDEX=OFF`, then use
`tests/fcfs_wall_pair.py ON_BINARY NEW_OUTPUT_DIRECTORY OFF_BINARY`. It runs a
fixed QD=16 cold 4-KiB fixture in ABBA/BAAB order, requiring identical raw virtual
traces on every repetition. The result is host execution efficiency for this
fixture, not a hardware throughput measurement or a general speedup guarantee.

## Recorded acceptance result

See [raw evidence and bounded results](../calibration/fcfs-index/README.md).
ON/CHECK each passed 34 CTest groups; Linux O1 CHECK ASan+UBSan passed all six Host
groups (113 donor cases plus two new races). Five production mutants were killed.
All 64 curve points completed, 56 prior raw outputs matched exactly, and 256
corrupt outputs were rejected. The paired QD=16 fixture improved median host wall
time from 4.851 to 2.873 s (1.689x); no virtual-time speedup is claimed.
