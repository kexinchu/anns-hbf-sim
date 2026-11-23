# Accepted multichannel functional evidence

GPU 0 is the final user-selected A6000; GPU 1 was tested separately before that
selection. Device CSV files preserve UUIDs. `sources.sha256` binds runtime sources
to these tests. Each JSON records arguments, exit status, stdout and stderr.

`cpu`, `cuda0`, `cuda1`: six directed recovery/race schedules plus two deliberate
mutations. `mapping`: 24 positive and four negative profiles. `sanitizer`: Linux
ASan/UBSan adapter/CPU harness (linked EventLab library is not instrumented).
`contract-report.txt`: unit-injected terminal failure, not actual permanent-media
failure. `ctest.txt`: complete local 19-test suite.

CUDA computes distances; CPU computes ordered top-10. EventLab transports symbolic
content with a separately checked byte sidecar. No timing calibration, performance
measurement or full OCP conformance is claimed.
