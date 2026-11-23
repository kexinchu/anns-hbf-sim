# Accepted functional evidence

`integrated/`: clean and ordered writeback real-CUDA/EventLab runs, three negative
runs, and sixteen CPU EventLab ACK/fault-replay traces including a bad-ACK mutation.
Device/compiler metadata and runtime-source hashes are included.

`lifecycle/`: thirty real-CUDA controlled traces and a corrupted-fill mutation,
with a separate source-hash manifest.

`sanitizers/`: Linux ASan+UBSan lifecycle and adapter differential outputs.
The adapter links an unsanitized EventLab library; instrumentation is not claimed
for that library. `ctest.txt` contains the local 16-test regression result.

All artifacts are functional validation; performance remains disabled. EventLab
models decoded commands/symbolic data; these are not physical HBF measurements.

`preliminary-integrated/` predates the explicit single-channel guard; its hashes apply only to those earlier traces. `integrated/` is final acceptance. `invalid/` retains development oracle/profile failures.
