# Contributing

1. Branch from main; describe the concrete bug or unsupported behavior.
2. Cite the relevant OCP clause or label the choice as a model assumption.
3. Add an independent oracle/analytical expectation and an adversarial case.
4. Run CTest and retain failing as well as passing artifacts.
5. Submit a pull request with scope, evidence and remaining limitations.

Do not change dependency pins without reviewing source differences and rerunning
upstream regression tests. Do not commit credentials, private data, machine logs,
third-party checkouts or binaries. Contribution licensing follows Apache-2.0.
Performance gates are separate from test success and require explicit review.
