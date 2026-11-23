# Target-specific observation protocol (frozen before execution)

Target selected by user: cloudsys01, NVIDIA RTX A6000. NVIDIA specifies 48GB
GDDR6, not HBM: https://www.nvidia.com/en-us/products/workstations/rtx-a6000/.
Use an idle GPU only; do not change clocks, ECC, persistence mode or other jobs.

Probe: one dependent pointer load per iteration, 64B-spaced nodes, seeded random
single-cycle permutation, 16MiB and 64MiB working sets, nodes+17 dependent loads (one full ring plus 17).
Use ld.global.cg to bypass L1; L2/TLB/interconnect/controller remain in the path.
For each size preserve one warmup (sample -1) and seven retained samples. Verify
final index against a CPU traversal. Record device/driver/ECC/clocks, CUDA compiler,
source SHA256, stdout, stderr and exit status. Device clocks may change during
execution; clock64 reports SM cycles, not DRAM cycles. CUDA event timing includes
kernel overhead. There is no timing-based pass/fail threshold in this observation.

These observations can constrain a future A6000 access-path model. They cannot
identify bank mapping, isolate row timing, calibrate HBM, or validate HBF errors.
No parameters are fitted and no held-out calibration result is claimed. Actual
calibration must predeclare its model, training/held-out sets and error limits.
ANNS performance experiments remain disabled.

The initial pilot used 65,536 loads and therefore visited only a subset of nodes.
It is retained under observations/a6000-pilot-20261123. Its allocation size must
not be interpreted as the touched working set. The full-ring revision above is
frozen before the next run; both remain observation-only, not calibrated timing.
