# ANNS HBF Simulator

A correctness-first research scaffold for ANNS across GPU, HBM and HBF.
**Experimental software: not an OCP-certified implementation, not a calibrated
hardware predictor. Performance experiments remain disabled.** GPU computation
is currently a synthetic resource; vector payloads are checked by a CPU sidecar.

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

## Development

Use branches and pull requests; run all tests before merging. New behavior must
include a clause or explicit model assumption, a reference/analytical test, and a
negative test that fails when the behavior is broken. Never turn a missing gate
into PASS by deleting the test. CI retains failing-run artifacts as well.

Apache-2.0 for project-authored code. See [third-party notices](THIRD_PARTY_NOTICES.md).
