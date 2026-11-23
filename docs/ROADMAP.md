# Roadmap

## Milestone 0.1 — Read-only baseline
- [x] Basic operating-system, architecture, CPU-count, memory, and Python runtime report
- [x] JSON output
- [x] Initial unit tests

## Milestone 0.2 — Hardware and graphics inventory
- [x] Windows CPU model, core/thread count, and clock information via CIM
- [x] Windows GPU model and driver information via CIM
- [x] DirectX registry version indicator
- [x] Vulkan ICD registration count
- [ ] Validate output on supported Windows versions and NVIDIA/AMD/Intel systems
- [ ] Add explicit DirectX feature-level and Vulkan device-capability probes
- [ ] Stable JSON schema and report versioning

## Milestone 0.3 — Compatibility test harness
- [ ] Declarative, read-only checks
- [ ] Reproducible test results with timestamps and environment metadata
- [ ] Exportable compatibility reports

## Later
- [ ] Optional user-approved tests for specific software
- [ ] Documentation for interpreting results
