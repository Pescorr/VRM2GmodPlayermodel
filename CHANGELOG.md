# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-27

### Added
- Initial public release
- Full 8-step conversion pipeline (VRM → GMod playermodel)
- VRM bone → ValveBiped remapping (68 bones)
- Mesh preparation with auto-combine, triangulation, and scale conversion
- A-pose conversion (T-pose → Source Engine A-pose)
- SMD/VTA export with flex animation support
- Proportion Trick (projected skeleton method)
- Smart material conversion with 3-tier texture fallback
- Physics model auto-generation (17 collision boxes)
- QC file generation with studiomdl compilation
- Lua playermodel registration file generation
- Flex/expression system with 96+ controller support
- Shape Key auto-detection with VRM standard expression mapping
- Post-conversion diagnostics (bone completeness, hierarchy, proportions, weights)
- Male/Female body type support
- Finger weight simplification (SIMPLE/DETAILED/FROZEN modes)
- Target height scaling
- Batch conversion via CLI
- Pure Python VTF writer fallback (no VTFCmd dependency required)
- Material texture override UI
