# Third-party components

Project-authored source and the EventLab overlay are offered under Apache-2.0.
Dependencies are fetched at immutable revisions in `pins.json`; their original
licenses remain in each checkout. They are not relicensed or bundled here.

- HBF-EventLab, sjtu-epcc: Apache-2.0. The build overlay modifies execution configuration,
  device driver and configuration serialization. `protocol_probe.cpp` also uses its
  bounded read result helper. https://github.com/sjtu-epcc/HBF-EventLab
- HBFSim, HBXim: MIT, Copyright (c) 2026 HBXim. HBM device and address heatmap reused.
  https://github.com/HBXim/HBFSim
- FlashLab and SlugLab entries are audit-only references; not required to build.

OCP specification text is not redistributed. See the official OCP specification
for its license and normative requirements. This project is not OCP-certified.
