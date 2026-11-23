# Device reset functional acceptance

GPU 0 was checked idle immediately before CUDA execution. device.csv records its
UUID; sources.sha256 identifies runtime sources. Every trace JSON contains input,
exit, stdout and stderr. CPU/CUDA/sanitizer outputs are compared in equivalence.txt.

The endpoint owns EventLab media/replacement components; full HostDriver and
DeviceDriver transport integration is not claimed. Unknown data refuses GPU work.
The concrete vector pattern is constructed from a known symbolic media token.

ASan/UBSan covers endpoint/harness code, not the linked donor static library.
All timing is synthetic. No hardware HBF reset, power failure or calibration was
measured; the real hardware evidence is A6000 CUDA distance execution.
