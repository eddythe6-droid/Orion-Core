# Roadmap

Project focus: evidence-backed research into Xbox-to-Windows PC platform portability. Hardware diagnostics are supporting utilities, not the project goal. This roadmap does not imply access to proprietary game source code or assets.

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

## Milestone 0.3 — Evidence-backed platform model
- [x] Validated evidence records with source provenance
- [x] Machine-readable capability inventory with schema version
- [x] Conservative Windows PC/Xbox support assessment; unknown remains unknown
- [x] Populate the inventory from official Microsoft GDK documentation
- [x] Add JSON CLI export for the curated capability catalogue
- [ ] Add schema compatibility tests and a documented schema migration policy

## Milestone 0.4 — Compatibility test harness
- [ ] Declarative, read-only checks
- [ ] Reproducible test results with timestamps and environment metadata
- [ ] Exportable compatibility reports

## Later
- [ ] Optional user-approved tests for specific software
- [ ] Documentation for interpreting results
