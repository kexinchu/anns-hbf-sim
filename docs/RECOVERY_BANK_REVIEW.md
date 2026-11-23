# Recovery, deadline and bank controller review

This change strengthens executable correctness evidence. It does **not** close
full OCP coverage or calibration gates. In particular, the new bank controller is
an isolated candidate backend, not silently substituted for the ANNS HBM backend.

## Normative requirements versus interpretation

Reference: [OCP HBF v0.7.0](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/).

| Clause | Independent test | Scope/interpretation |
|---|---|---|
| §5.4.1(6), §11.5.2.5 | Last fragment at deadline−1, deadline, deadline+1, direct/nested arrival | Six cases. Same-tick arrival precedes deadline settlement is the explicit EventLab policy; the spec does not prescribe simulator event phases. |
| §11.5.2.6–7 | Failed page status 7; accepted followers status 6/info2; drain errors before replay | Whole-page burst writes; one response per command. Post-failure follower remains on the failure path, not ordinary info1 missing-predecessor. |
| §11.5.2.7 | Host-owned replay payload from page 0 through failed page, early follow-up blocked | Reusable and unusable failures at pages 0/1/3; read-back validates restored tokens; old followers must be resubmitted. |
| §11.5.2.7 | Failure again at page 0 during replay of page 3 | Original replay endpoint remains 3; a smaller later failure cannot discharge earlier replay debt. |
| Table13, §11.5.2.8 | One spare used, second unusable failure exhausts it; status8/info1 then status1 | Block-level retirement. Info1 encodes NAND-block granularity, not generic success/default metadata. |

Seven recovery traces compare admission, credit counts, response IDs, status,
additional information, physical block identity and read-back tokens after every command/control step.
The Python reference never imports donor state. Two initial oracle omissions
(info2 propagation and block-retirement info1) were corrected against these
clauses, with failed traces retained locally. No mismatch was hidden by removing
its test. E/P/F/U/D are controlled environment actions, not wire commands.

The tests validate a successful recovery sequence and the tested failure exits.
They do not implement a complete autonomous host recovery manager. Outstanding
work includes CECC/UECC, read-retry/refresh, erase-fail, die-level recovery,
asynchronous multi-bank faults, reset persistence and mixed remapping races.
These remain unsupported or unverified, **not PASS**.

## Bank-level online candidate

`BankHbm` is a separate explicit-cycle state machine. At each cycle the caller
submits arrivals, then calls `step`; skipped cycles and past/future admissions
are rejected. Completion retirement precedes command scheduling but follows
that cycle's admission, so same-tick released credit is available next cycle.
No call pumps a burst to a guessed future completion.

- Four banks in one pseudo-channel in the probe; finite eight-entry resident limit.
- FIFO within each bank, ready-column-first across banks; after 32 cycles an aged
  ready request takes priority. This is not unrestricted FR-FCFS within a bank.
- Explicit ACT/PRE/RD/WR, shared single-command bus and serialized data bursts.
- tRCD, tRP, tRAS, tRC, tRRD, four-activate window, tCCD, read/write turnaround,
  read-to-precharge and write recovery gates are enforced in synthetic cycles.
- Completion releases credit exactly once, after the data burst ends.

The model deliberately has no refresh, bank-group-specific timings, PHY, ECC,
HBM address mapping, split parent accesses or multiple pseudo-channels yet.
Its fixed small timings are test parameters and **not a JEDEC device profile**.
OCP HBF does not specify the GPU's HBM timing. Do not call this candidate a
validated HBM3/4 replacement; existing HBXim and PC-level fixtures remain intact.

35 traces (3 directed, 32 seeded with 80 arrivals each) compare every command
against an independent Python cycle interpreter. An additional checker verifies
command/data-bus exclusion, tRCD/PRE/ACT/turnaround gates and conservation without
reimplementing arbitration. Hand calculations establish cold completion at cycle
10 and two-bank overlap completing at cycle12. Deliberate early completion must
fail. These are software consistency checks, not physical calibration.

## Research acceptance

Passing these tests supports the declared subset only. Before integrating this
bank controller into ANNS: add refresh/bank groups, address/split-parent adapters,
parameter provenance and differential checks against an established DRAM model.
Before performance: full workload dependency/real GPU validation, relevant fault
coverage and held-out calibration are still required. `performance_ready=false`.

## 2026-11-23 extension: host policy and ANNS bank adapter

`anns_loop_bank` now routes the existing ANNS fixture's producer reads, page fills,
consumer reads and result writes through `BankAdapter` and `BankHbm`. The serial
and PC-level executables are retained as controls. This closes the *functional
adapter* gap, not the HBM fidelity or calibration gate. All three remain CPU
fixtures, not GPU instruction execution. The bank adapter uses synthetic 64-byte
interleaving, four banks, 1KiB rows and 1ns cycles; only address-space capacity is
read from HbmConfig. Other donor HBM timing/geometry settings do not configure it.

Parent admission is atomic and bounded; unaligned accesses split at burst
boundaries. Parents complete once all children finish. Data-bus receipts count
physical bytes. Idle cycles advance controller time; callbacks cannot pump a
future completion. Admission becomes schedulable on the next cycle (explicit
adapter policy). The first integration test exposed a same-tick HBF pause error;
next-cycle admission fixes it without relaxing the existing checker.

`ReadRecovery` is a **host-policy component**, exercised by injected responses.
It is not wired into EventLab's read response transport yet. No NAND bit-error
rate, ECC code, decoding latency or physical die recovery algorithm is claimed.

| OCP v0.7 reference | Added executable evidence | Remaining gap |
|---|---|---|
| Table 12, §11.5.1.4 | UECC invalid payload rejected; backup required; block quarantined | Device ECC/fault propagation and backup data validation |
| Table 12, §11.5.1.5 | CECC valid data delivered with refresh obligation | Corrected payload still needs real transport integration |
| §11.5.1.6 | All 3-bit retry stages retained; bounded attempts; invalid payload rejected | Retry stage is exposed to caller, not yet encoded into EventLab ARuser |
| §11.5.1.4–5 | Refresh requires backup and drained readers; sequential page acknowledgements; failed refresh remains dirty | Real erase/program/read-back transaction and persistent journal |
| §11.5.1.8 | Block/bank/die/channel retirement scopes prevent subsequent admissions | Device CSR bitmap persistence and in-flight retirement races |
| §11.5.1.9 | Die-wide read/write admission block; independent die continues; only ready poll unblocks | Actual CSR command transport; asynchronous outstanding-command draining |

The three-retry cap, strict block quarantine after CECC, two-die test topology,
and caller-supplied refresh page count are model/host-policy choices, not OCP
mandates. `page_written` must eventually be driven by verified write completions;
its present injected acknowledgements are not proof of media refresh. Tests use
independently specified action transcripts, not an independently coded ECC engine.

## Calibration remains blocked

No target GPU/HBM part or held-out device trace is identified for this extension.
The upstream [Ramulator HBM3 implementation](https://github.com/CMU-SAFARI/ramulator2/blob/main/python/ramulator/dram/hbm3.py)
is a useful reference for the missing bank-group, refresh and directional timing
constraints. Its presets are model inputs, not measurements of our target GPU.
Copying those numbers into this simpler controller would not establish calibration.

Required before clearing the gate: identify part/clock/topology; pin parameter
sources and units; implement unsupported timing constraints; compare command
legality against an independent established model; then validate held-out
row-hit/conflict, multi-bank, read/write and refresh-contention observations with
predeclared error bounds. GPU caches and address mapping must be controlled or
explicitly included. Do not run ANNS performance experiments to fit these values.
`performance_ready=false`; no full-OCP compliance claim.
