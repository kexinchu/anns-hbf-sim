# ANNS HBF Simulator

A correctness-first research scaffold for ANNS across GPU, HBM and HBF.
**Experimental software: not an OCP-certified implementation, not a calibrated
hardware predictor. Performance experiments remain disabled.** EventLab GPU computation
is a synthetic resource with CPU-side payload checks. The separate A6000 functional
path executes real CUDA distance/top-k and event-gated page lifetimes; it does not
calibrate HBM/HBF. The optional integrated CUDA target now follows EventLab
Host/Device command responses; it does not model serialized AXI/UCIe packets.

See [versioned page lifecycle acceptance](docs/PAGE_LIFECYCLE_REVIEW.md) for
finite frames, refresh/read races, writeback failure and die isolation evidence.

See [writeback token/epoch and EventLab review](docs/WIRE_ACK_REVIEW.md) for the
current integration scope and remaining gates.

See [multichannel groups and joint recovery/CUDA review](docs/MULTICHANNEL_REVIEW.md)
for the complete-group API and combined fault/race validation scope.

## Reproduce

Requires Python 3, Git, CMake >=3.20 and a C++20 compiler. No GPU required.

```sh
python3 bootstrap.py
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON
cmake --build build -j 4
ctest --test-dir build --output-on-failure
```

Pinned public dependencies are downloaded into ignored `vendor/`. No upstream
source is edited. The explicit EventLab overlay is generated into the build tree.
Every differential/closed-loop run saves inputs, outputs and configuration in a
unique subdirectory of the build tree. Existing evidence is never overwritten.

## Components and tests

- Independent Python protocol reference and C++ public-API probe: compare every
  command's admission, outstanding count, visible responses and payload tokens.
- Finite shared Core Channel: FIFO half-duplex serialization and propagation;
  read cache visibility follows page transfer completion.
- Online bounded HBM: FIFO per pseudo-channel, one burst in flight per lane,
  parallel independent lanes, atomic admission and one completion per parent.
- Serial and concurrent CPU IVF/rerank fixtures: independent top-k oracle,
  byte conservation, causal visibility, resource lifetime and fault mutations.
- Analytical resource checks and OCP configuration checks.

See [protocol and resource assumptions](docs/protocol-and-resources.md) and
[research acceptance gates](docs/ACCEPTANCE.md). The reference covers a declared
subset; it is not a complete executable OCP specification. Explicit P/D/T probe
actions control media completion, response delivery and timeout drainage; they
are test controls, not wire commands. Cache/order resource tests supplement the
protocol reference and are not a second complete protocol implementation.

## Scope that must not be hidden

HBM parallelism is across pseudo-channels, not a complete bank-level FR-FCFS
controller. Core transfer parameters are assumptions, not OCP-calibrated numbers.
Die-port contention, full AXI/UCIe, error recovery/ECC, thermal effects, GPU data
migration and held-out hardware calibration remain incomplete. Correct software
under these assumptions does not establish accurate device performance.

Normative reference: [OCP HBF v0.7.0, August 3, 2026](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/).

## Additional correctness modules

See [recovery/deadline/bank review](docs/RECOVERY_BANK_REVIEW.md). The new bank-level
controller is an isolated candidate with synthetic cycle timings; the production
ANNS fixture still uses the explicitly bounded PC-level model.

## Development

Use branches and pull requests; run all tests before merging. New behavior must
include a clause or explicit model assumption, a reference/analytical test, and a
negative test that fails when the behavior is broken. Never turn a missing gate
into PASS by deleting the test. CI retains failing-run artifacts as well.

Apache-2.0 for project-authored code. See [third-party notices](THIRD_PARTY_NOTICES.md).

### Bank adapter and read recovery policy

`anns_loop_bank` integrates the cycle-stepped bank backend into the same ANNS
functional dependency path. `read_recovery_probe` separately tests OCP read-error
host actions; it does **not** yet implement device ECC or transport retry metadata
through EventLab. See [the extension audit](docs/RECOVERY_BANK_REVIEW.md).
All timings remain uncalibrated and performance experiments remain disabled.

Reset/cancel and permanent-failure functional scope: [review](docs/RESET_CANCEL_REVIEW.md). Physical die reset and calibration remain open; performance stays disabled.

The [device reset review](docs/DEVICE_RESET_REVIEW.md) documents the standalone endpoint. The [full DeviceDriver review](docs/DRIVER_RESET_REVIEW.md) documents physical reset integration through actual links, queues, assembly, bank service and feedback, its independent tests and remaining OCP/model gaps. Performance remains disabled.

The [external reset review](docs/EXTERNAL_RESET_REVIEW.md) extends validation to post-recovery packets, request-ID reuse and distinct CSR reset profiles; all hardware/performance calibration gates remain closed.
