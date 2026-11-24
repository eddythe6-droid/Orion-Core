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
- [x] Add native Windows D3D12 feature-level and capability probe (runtime validation pending)
- [ ] Add explicit Vulkan device-capability probe
- [x] Versioned diagnostic JSON report envelope with UTC timestamp and environment metadata
- [ ] Validate output on supported Windows versions and NVIDIA/AMD/Intel systems

## Milestone 0.3 — Evidence-backed platform model
- [x] Validated evidence records with source provenance
- [x] Machine-readable capability inventory with schema version
- [x] Conservative Windows PC/Xbox support assessment; unknown remains unknown
- [x] Populate the inventory from official Microsoft GDK documentation
- [x] Add evidence-backed input, save-data, common file-I/O, audio, networking, and packaging contracts
- [x] Add JSON CLI export for the curated capability catalogue
- [ ] Add schema compatibility tests and a documented schema migration policy

## Milestone 0.4 — Compatibility test harness
- [x] Initial hardware-independent graphics lifetime simulator (queue/fence, residency budget, descriptor retirement)
- [x] Resource transition state tracker (simulation only; runtime GPU validation not implied)
- [x] Per-subresource transition state tracker (simulation only)
- [ ] Declarative, read-only checks
- [x] Timestamped diagnostic report with environment metadata
- [x] Validate and normalize native D3D12 probe JSON with explicit unknown handling
- [x] Compare two native D3D12 adapter reports conservatively (feature tiers, boolean features, raw format masks)
- [x] DXGI local/non-local memory budget snapshot and conservative pressure summary
- [x] Deterministic GPU memory allocation-pressure simulation (not a driver emulator)
- [x] Deterministic priority-based resource streaming and eviction policy simulation
- [x] Fence-aware upload lifecycle simulation with pending resources protected until copy-fence completion
- [x] Multi-queue fence tracking and deferred resource retirement simulation
- [x] Explicit inter-queue producer-fence wait model with dependency-cycle detection (simulation only)
- [x] Integrate explicit queue dependencies into the GPU resource manager (simulation only)
- [x] Fence-aware descriptor heap range allocator with multi-queue retirement (simulation only)
- [x] Integrate descriptor heap lifetime into GPU resource manager snapshot
- [x] Resource writer-queue ownership tracking with fence-linked handoff records (simulation only)
- [x] Declarative graphics pipeline description and structural validation (native PSO validation pending)
- [x] Shader feature requirement assessment against reported D3D12 probe capabilities (bytecode validation pending)
- [x] Preserve and compare raw render-target/texture format support query masks without guessing flag semantics
- [x] Resource-binding tier requirement assessment
- [x] Unified graphics compatibility research report (native validation pending)
- [x] Declarative D3D12 root-signature layout and DWORD cost validation
- [x] Integrate root-signature structural checks into unified graphics report
- [ ] Reproducible runtime test results with timestamps and environment metadata
- [x] Evidence-linked target compatibility assessment (compatible/adaptable/platform-specific/unknown)
- [x] CLI JSON export and subsystem filtering for compatibility reports
- [ ] Reproducible hardware test results with timestamps and environment metadata
- [ ] Exportable compatibility reports
- [x] Native minimal HLSL compilation, graphics PSO creation, off-screen draw, and pixel readback smoke test (hardware runtime validation pending)
- [ ] Render-target format support interpretation using verified SDK flag definitions
- [x] Native minimal root-signature serialization/creation smoke test (runtime result captured per adapter)
- [x] Native shader-visible CBV/SRV/UAV and sampler descriptor heap creation smoke tests
- [x] Populate a CBV descriptor and bind descriptor heap/root table on a native graphics command list (runtime validation pending)
- [x] Native resource-binding validation smoke test with root signature, CBV descriptor heap, shader consumption, and pixel readback (runtime validation pending)
- [x] Native root-signature serialization and graphics PSO creation smoke tests (runtime validation pending)

## Desktop application
- [x] Initial Tkinter desktop dashboard with system inventory cards
- [x] Live event-driven console with severity colors, auto-scroll, and clear action
- [x] Save console log and export diagnostic JSON
- [x] Launch a user-selected native D3D12 probe executable and validate its JSON report
- [x] Include native GPU probe data in the combined diagnostic JSON export
- [x] Stream native `[ORION_PROGRESS]` events from standard error into the live console
- [ ] Add dedicated GPU, memory, CPU, evidence, and compatibility views
- [x] Add local PE import-to-export cross-reference with ambiguity, architecture, ordinal and forwarder states
- [x] Add delay-load module presence checks (delay-load symbols remain unparsed)
- [x] Add curated exact-name Win32 API family catalogue with explicit non-equivalence warnings
- [x] Add searchable dependency table, selection details, separate file/folder pickers and analysis progress indicator
- [x] Add guided Game Inspector workspace with file/folder picker, asynchronous analysis, PE dependency/export summary and JSON export
- [ ] Package a Windows desktop build and validate on physical hardware

## Game-file research
- [x] Read-only directory/file inventory with basic signature detection
- [x] Metadata-only ZIP member listing without extraction
- [x] Optional bounded SHA-256 hashing and JSON inspection reports
- [x] Parse core PE headers, sections and imported DLL names with bounded read-only parser
- [x] Parse bounded PE export tables, names, ordinals and forwarder strings\n- [x] Add separate Xbox Series / Scarlett PE32+ x64 candidate assessment with conservative GDK import-name hints (not authenticity verification)
- [x] Research and parse public XContent/STFS metadata headers (`CON `, `LIVE`, `PIRS`) without signature/hash verification
- [x] Identify common GOD/SVOD sibling header + `.data/DataNNNN` layout by metadata only
- [x] Parse documented public XEX2 wrapper metadata (fixed header, optional-header directory, entry point/base and execution info)
- [ ] Validate XEX2/STFS/SVOD parsers against lawful, unprotected samples; payload decoding remains out of scope
- [x] Add read-only ISO9660 volume and recursive directory inventory
- [ ] Add read-only parsers for documented asset/container formats

## Later
- [ ] Optional user-approved tests for specific software
- [ ] Documentation for interpreting results


## Game image inspection progress (2026-11-23)

- [x] Read-only ISO9660 volume and directory inventory.
- [x] Read-only XDVDFS/XISO volume descriptor and binary-tree directory inventory for standard sector-32 and rebuilt sector-0 layouts.
- [x] Detect common XGD1/XGD2/XGD3 game-partition offsets; hybrid and variable-offset variants remain open.
- [x] Inspect STFS/XContent public metadata and distinguish STFS vs SVOD descriptor types.
- [x] Identify GOD/SVOD sibling data-file layout without processing payload/hash tables.
- [x] Parse public XEX2 wrapper metadata and integrate it into Game Inspector.
- [ ] Parse XEX import-library and resource metadata after additional cross-checking against independent implementations.
- [ ] Verify SVOD block/hash-table layout against independent public specifications and lawful samples; payload reconstruction intentionally out of current scope.
- [ ] Validate parsers against legally obtained, unprotected sample images and record format coverage.

Current parser scope and limitations: see `GAME_INSPECTOR.md`, `XDVDFS.md`, `XEX2.md`, and `SCARLETT_PE.md`.
