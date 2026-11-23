# Validation record — 2026-11-23

Scope: CPU software contracts and explicitly declared uncalibrated resource model.

- Independent protocol differential: 16 seeds, 12,504 commands/control steps.
  Includes incomplete-page timeout, old erase lifetime, retry generations, response
  delivery, credit exhaustion, pending forwarding, overlap and explicit ID groups.
- Serial and concurrent IVF/rerank: five fixtures each, independent Python top-k
  and causal/byte checks, deliberate invalid payload/address/visibility mutations.
- Resource checks: cold HBM analytical expectation, same-lane exclusion,
  independent-PC overlap, atomic bounded admission, one completion per parent;
  finite Core cold-page cost, shared-link contention, independent-link overlap,
  same-bank ordering and two retained cache pages.
- OCP configuration checks: supported and reserved decoded MOCS values, limits,
  declared profile and serialization roundtrip.

Initial timeout expansion found two oracle omissions: pending erase lifetime and
retention of completed erase across retries. The state model was expanded rather
than removing the scenario. Read backpressure during erase is an explicit adapter
policy, not a normative timing mandate. Exact deadline races are still outside
this test. Raw traces are regenerated and retained by CTest/CI.

A test-step count is not a clause-coverage percentage. Seed variation is not
exhaustive model checking. None of these results validate physical HBF latency,
real GPU residency, whole-library recall, P99, throughput or power.
