# Orion-Core

Orion-Core is an experimental, read-only Windows diagnostics and software-compatibility research toolkit.

## Requirements

- Python 3.10 or newer
- Basic system report: Windows, Linux, or macOS
- Extended CPU/GPU and graphics-runtime inventory: Windows with PowerShell and access to the local Windows registry

## Run

From a source checkout:

```bash
python -m pip install -e .
python -m orion_core
```

Machine-readable report:

```bash
python -m orion_core --json
```

## Desktop dashboard

Launch the desktop interface on Windows:

```bash
orion-core-gui
```

Or from a source checkout:

```bash
python -m orion_core.gui
```

The dashboard includes a live event console, read-only system inventory cards,
log saving, and JSON report export. Its current scan reports real collector
events for OS/CPU/memory and Windows CIM/registry inventory. It does not yet
launch the native D3D12 GPU workload test; the UI labels that limitation rather
than displaying simulated GPU progress. The interface uses Python's built-in
Tkinter and adds no third-party runtime dependency.


Skip Windows-specific inventory:

```bash
python -m orion_core --basic-only --json
```

## Windows inventory scope

The current Windows collector reads CPU and display-adapter properties through CIM, the DirectX registry version, and the count of registered Vulkan ICD manifest entries. These are diagnostic indicators, not a certification of game compatibility or a complete DirectX feature-level/Vulkan capability test. Missing data is reported rather than guessed.

The tool is read-only: it does not change registry values, install software or drivers, run downloaded executables, or collect device serial numbers, MAC addresses, usernames, hostnames, or personal files.

See [ROADMAP](docs/ROADMAP.md), [SAFETY](docs/SAFETY.md), and the [agent team charter](docs/AGENT_TEAM.md). Role prompts for compatible coding-agent environments are stored in `.github/agents/`.

## Platform capability catalogue

Export the curated, source-backed Xbox/Windows PC capability inventory:

```bash
python -m orion_core --capabilities-json
```

The catalogue distinguishes documented common APIs from platform-specific extensions and preserves unknowns rather than guessing. It describes public platform contracts, not the implementation details of any particular game. See [the capability research report](docs/RESEARCH_CAPABILITY_CATALOG.md).

## Synthetic graphics harness

A hardware-independent model for D3D12-inspired queue/fence lifetime, residency-budget and descriptor-range invariants is available in `orion_core.graphics_harness`. It is a simulator for testing Orion-Core abstractions, not a GPU driver or Xbox emulator. See [the harness notes](docs/GRAPHICS_HARNESS.md) and [the graphics deep dive](docs/RESEARCH_GRAPHICS_DEEP_DIVE.md).

## Native Windows D3D12 probe

A read-only C++ probe is available under `native/d3d12_probe`. It queries public Windows D3D12 adapter capabilities and performs a minimal queue/fence check. See [build and scope notes](docs/NATIVE_D3D12_PROBE.md). Windows CI compiles it; physical GPU execution must be validated separately.
