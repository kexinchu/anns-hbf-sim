# Device physical addressing, CSR reset, and uncertain media

Performance remains disabled. `ResetDevice` is a new **device-side functional
endpoint**, not an extension of `VersionedPages::block` or the old `page / 4`
host-domain fence. It owns media, physical replacement state, outstanding programs,
channel registers, boot state and completion identities. The previous host-domain
implementation remains a separate historical test path.

## Reused components and actual scope

The address chain is EventLab `RoundRobinInterleaver` -> `ReferenceAddressLayout`
-> `BlockReplacement`. This fixture uses identity zone mapping. The configured
reference layout is [block][page][die][bank], with two channels, two dies/channel,
two banks/die, four pages/block, two nominal blocks/bank, one spare/bank, a 4096-byte
global base and 64-byte stripes. Replaced blocks stay on the same channel/die/bank;
tests inspect the new physical block and access its distinct data.

Actual page storage and program order use EventLab `NandMediaState`. The endpoint
accepts an already assembled local 4KiB page, with an immutable physical target and
completion due tick. It does not use the full EventLab HostDriver splitter,
DeviceDriver queues, AXI packet codec or Core Channel timing. In particular, a
global address here identifies a local page via its first fragment; it is **not**
a claim that the following global 4KiB is contiguous on one channel. Dynamic zone
swaps and fragmented assembly interrupted by reset are not implemented here.

The GPU probe consumes a known media token, constructs the documented concrete
vector pattern, and computes 32 integer distances using the existing CUDA backend.
This is a device-to-GPU functional consumption path, not serialized vector bytes
through media, production ANNS, or a completed replacement for the existing ANNS
transport. Unknown/erased/blocked reads produce no GPU work. CPU and CUDA run the
same command traces, checked by an independent Python reference.

## Device state and model choices

- Power-on starts boot with EN=0 and RDY=0; modeled boot completion raises RDY.
  Device admission requires power, RDY, EN and availability of the mapped die.
- Implemented CSR subset: BUCC offset 0x0c EN; BUCSTS 0x10 RDY;
  BUCR 0x14 key/type. Bad reset keys have no effect. Reserved reset fields/types,
  unsupported BUCC fields and read-only/unsupported writes are rejected.
- All valid channel resets advance response identity, lower RDY and restart boot.
  Warm reset also disables EN and aborts pending media programs. The type 0/1
  functional profile retains EN and lets scheduled core programs finish; these
  are explicit retention choices, not a modeled PHY/D2D/AOU implementation.
- Pending programs at **any** channel reset taint their physical blocks. A later
  simulated completion cannot clear uncertainty. Die-fault reset aborts only the
  physically addressed die, advances its identity and blocks it until recovery.
  The die-fault API is an injection hook, not an invented OCP CSR address.
- Power loss aborts all pending programs and invalidates response identities.
  Boot does not clear uncertain media. Previously completed media is retained in
  this non-security, no-power-on-erase profile. This is not a durability guarantee
  for a real product, nor a rail-level power or torn-cell model.
- Uncertainty is a conservative knowledge state covering the **whole affected
  physical block**. Reads return `unknown`, never assumed old/new/zero data.
  Erase plus ordered rewrite can restore known data. No probability or concrete
  torn-write outcome is inferred from OCP. Collateral corruption outside the
  affected block is outside this profile.
- Completed-but-undelivered responses are independently tagged. Reset can make
  an ACK stale while its completed media remains known. Aborted operations cannot
  finish later. IDs remain non-reusable for the endpoint lifetime.

Boot/recovery=5 and program=10 are arbitrary functional ticks; advancing virtual
time completes modeled device events, never a CUDA event. No tick is calibrated.
Metadata is retained for these finite tests; production reclamation is not modeled.

## OCP review

Primary source: [OCP HBF v0.7.0](https://www.opencompute.org/documents/ocp-hbf-architecture-specification-v0-7-0-final-pdf/), inspected 2026-11-23.

| Clause | Implemented check | Remaining boundary |
|---|---|---|
| §4.6, §5.7 | Explicit channel/die/bank/block/page and physical replacement | Reference layout and identity zones, not a universal vendor mapping |
| §5.9.2.3–5 | EN/RDY and BUCR key/type behavior | Other fields, actual PHY/D2D/AOU and serialized CSR access absent |
| §7.3 | Unsafe reset leaves pending writes uncertain; delayed ACK invalidation | Safe host drain is a separate policy; no electrical/reset pulse certification |
| §7.4, §7.6 | Power/boot/admission sequencing and interrupted-write state | No voltage ramps or analog power-loss model |
| §11.5.1.9, §11.5.2.9 | Availability follows physical die coordinates | Die status injection is not a CSR polling implementation |
| §11.5.2.7–8 | Donor physical replacement reused | Permanent-failure campaign remains in the previous EventLab test path |

The specification does not supply all implementation-specific reset retention or
power-loss details. Those choices above remain assumptions requiring vendor review.
Passing tests establishes consistency with this declared functional profile, not
full OCP conformance or measured HBF device behavior.

## Independent and negative tests

Twelve traces cover 128 physical address/offset mappings, warm/link reset, die reset
and power loss both before and after program completion, other-die/channel data,
delayed/duplicate ACKs, uncertain-read refusal, erase/rewrite, and spare remapping.
Directed invalid commands cover reserved CSR values, wrong keys, out-of-range
coordinates, boot/disabled admission, reused IDs and erase/remap while busy.
The reference enumerates physical tuples to construct global addresses and models
register/media states without importing C++ or using captured output as a golden.

Three deliberate mutations must exit normally and be detected: publishing unknown
data, aliasing physical dies, and reporting RDY before boot. Device and reference
comparisons cover every emitted command result, map coordinate and GPU score.

```
cmake -S . -B build
cmake --build build -j4
ctest --test-dir build --output-on-failure
ANNS_GPU_INDEX=0 bash gpu/run_device_reset.sh
```

The script checks GPU occupancy, records UUID/source hashes, and runs CPU, CUDA and
ASan/UBSan suites separately. Sanitizers instrument the new endpoint/probe; linked
EventLab library code is not instrumented.

## Accepted results (2026-11-23)

[Raw evidence](../gpu/evidence/a6000-device-reset-20261123/) records the selected
A6000 GPU 0 UUID, idle check, hashes and every trace. Local CTest passed 21/21;
the final device test was rerun after adding mutations. CPU, CUDA and Linux
ASan/UBSan each passed 12 traces, 128 mapping checks and all three deliberate
mutations. Positive command outputs match byte-for-byte across the three backends.
This validates the declared functional endpoint, not physical HBF reset behavior.
