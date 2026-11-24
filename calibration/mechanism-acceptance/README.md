# Mechanism acceptance, 2026-11-23

[Source-backed acceptance audit](../../docs/MECHANISM_ACCEPTANCE_ZH.md).

The new public-path fixture and independent Python checker pass 262 quiescent
cache-reference phases and eight directed runs. Five corrupted traces and two
compiled production cache mutants are rejected. Full CTest: 35/35 passed.
The previous published FCFS revision's GitHub CI also completed successfully
(run 45298164830); that is not a CI verdict for this new revision.

The `sense-media-finish` observation separates actual media completion from the
existing `sense-finish` buffer-ready/bank-release boundary. No timing parameter
or scheduling behavior was changed. All timing probes are model observations,
not hardware measurements. LRU and Core FIFO are declared assumptions, not an
OCP-wide certification result. Cold saturated throughput matching, normative
victim interpretation, and HAVEN compute/power closure remain open.

Raw inputs, outputs, binary/source hashes, CTest results and mutation rejections
are in `20261123/`. No performance experiment was enabled.
