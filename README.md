# Orion-Core

**Orion-Core** is an experimental, read-only research toolkit for inspecting Xbox game media and studying the technical work required to assess Windows-PC compatibility. It combines Windows hardware diagnostics, a native Direct3D 12 probe, platform capability research, and metadata-only game-image inspection.

> **Current scope:** this is a research and inventory tool, not an Xbox emulator, game port, compatibility guarantee, or installer. It does not decrypt protected content, bypass DRM, patch signatures, extract game payloads, or execute files discovered during inspection.

## What it can do

### Game Inspector

The desktop dashboard opens directly into the **Game Research Lab**: choose a directory, EXE/DLL, ISO/XISO or supported package, inspect locally, review the media inventory and Xbox Series PE evidence, then export the full JSON report. The interface does not execute discovered files. The live console supports a **Копировать** button, selection/full-log context menu, Ctrl+A and Ctrl+C.

The Game Inspector creates a JSON inventory from a game directory, a supported disc image, a package file, or a ZIP archive.

| Format / source | Current inspection |
| --- | --- |
| Directories | Recursive file inventory, signatures, extensions, optional bounded SHA-256 |
| ZIP | Member names and sizes; no extraction |
| ISO9660 | Volume and directory metadata |
| XDVDFS / XISO | Volume descriptor and directory tree |
| Xbox disc layouts | Known common XGD1, XGD2 and XGD3 partition offsets, plus bare/rebuilt XISO |
| Xbox 360 XContent / STFS | Public metadata in `CON `, `LIVE`, and `PIRS` headers |
| Xbox 360 GOD / SVOD | Conservative detection of the sibling header + `.data/DataNNNN` layout; file names and sizes only |
| Xbox 360 XEX2 | Public wrapper metadata, optional-header directory, entry point, image base and execution information |
| Windows PE | PE/COFF headers, data directories, section flags and bounds, named/ordinal imports, normal and delay-load Xbox/GDK dependency evidence, bounded Authenticode certificate-table framing, curated Win32 API families, graphics-stack dependencies and bounded DXBC/DXIL/SPIR-V shader metadata |

The parsers are deliberately read-only. XEX2 inspection does not decrypt or decompress the wrapped PowerPC image. STFS/SVOD inspection does not validate package signatures, process hash tables, or reconstruct payload files. A detected signature or layout is evidence for further investigation, not proof that a complete or valid game has been parsed.

### System and graphics diagnostics

- Basic OS, CPU and memory report on Windows, Linux and macOS.
- Extended Windows CPU/GPU and graphics-runtime inventory.
- Native C++ Direct3D 12 probe under `native/d3d12_probe`.
- GPU adapter capabilities, memory budgets, queues/fences, resource operations and a small render/readback workload.
- Desktop dashboard with live events, diagnostics history and JSON export.

The native D3D12 probe performs real operations on the Windows GPU. The Python graphics harness is a hardware-independent model for testing Orion-Core's abstractions; it is not a GPU emulator.

### Platform compatibility research

The curated capability catalogue links documented platform capabilities to evidence and preserves unknowns rather than inventing compatibility. It describes platform APIs and constraints, not the internals of a particular game.

### Current case study: GTA VI Xbox Series

Evidence status, published reference hashes, Xbox Series vs Xbox 360 format distinction, and the safe static-analysis plan are documented in [GTA6_XBOX_SERIES_CASE](docs/GTA6_XBOX_SERIES_CASE.md). The reported executable has not been independently obtained or validated by Orion-Core.

## Requirements

- Python 3.10 or newer.
- Basic diagnostics: Windows, Linux or macOS.
- Extended Windows inventory and native D3D12 probe: Windows; the native probe requires a suitable Visual Studio C++ toolchain and Windows SDK.
- Pytest is used for development tests.

## Install and run

From a source checkout:

```bash
python -m pip install -e .
python -m orion_core
```

Machine-readable system report:

```bash
python -m orion_core --json
```

Skip Windows-specific inventory:

```bash
python -m orion_core --basic-only --json
```

Launch the desktop dashboard:

```bash
orion-core-gui
```

or:

```bash
python -m orion_core.gui
```

## Inspect game files

Inspect a directory recursively:

```bash
python -m orion_core --inspect-game-path "D:\\Games\\Example" --inspect-output ".\\game-inventory.json"
```

Inspect a disc image:

```bash
python -m orion_core --inspect-game-path "D:\\Images\\game.iso" --inspect-output ".\\game-inventory.json"
```

Inspect a package or XEX file:

```bash
python -m orion_core --inspect-game-path "D:\\Games\\default.xex" --inspect-output ".\\xex-report.json"
python -m orion_core --inspect-game-path "D:\\Packages\\content"
```

Optional SHA-256 for ordinary files is limited to files no larger than 64 MiB:

```bash
python -m orion_core --inspect-game-path "D:\\Games\\Example" --inspect-hash-files
```

A separate opt-in GUI option enables streaming SHA-256 for PE, XEX2 and XContent/STFS executable/package candidates regardless of file size; this can take a long time for very large files. The inspector reports detected formats, PE data-directory/section metadata, certificate-table framing, import dependency hints, file sizes, parser warnings and explicit scope flags. It does not mount images or unpack archives.

## Native Direct3D 12 probe

Source and build notes are in [NATIVE_D3D12_PROBE](docs/NATIVE_D3D12_PROBE.md). The dashboard can launch a previously built probe executable without invoking a shell, stream progress messages, validate its JSON output and attach the result to a combined report.

Windows CI compilation is not a substitute for running the probe on physical hardware. Actual GPU behavior must be tested on the target PC.

## Platform capability catalogue

Export the curated Xbox/Windows PC capability inventory:

```bash
python -m orion_core --capabilities-json
```

Create an evidence-linked target assessment:

```bash
python -m orion_core --assess-target windows_pc
```

See [RESEARCH_CAPABILITY_CATALOG](docs/RESEARCH_CAPABILITY_CATALOG.md).

## Research and documentation

- [Roadmap](docs/ROADMAP.md)
- [Game Inspector](docs/GAME_INSPECTOR.md)
- [XDVDFS / XISO](docs/XDVDFS.md)
- [Xbox 360 XEX2 metadata](docs/XEX2.md)\n- [Xbox Series / Scarlett PE analysis](docs/SCARLETT_PE.md)
- [PE dependency triage](docs/PE_DEPENDENCY_TRIAGE.md)
- [PE export analysis](docs/PE_EXPORT_ANALYSIS.md)
- [PE import resolution](docs/PE_IMPORT_RESOLUTION.md)
- [Win32 API symbol catalogue](docs/API_SYMBOL_CATALOG.md)
- [Graphics dependency analysis](docs/GRAPHICS_DEPENDENCIES.md)\n- [DXBC/DXIL/SPIR-V shader inspection](docs/SHADER_INSPECTION.md)
- [Native D3D12 probe](docs/NATIVE_D3D12_PROBE.md)
- [Graphics harness](docs/GRAPHICS_HARNESS.md)
- [Graphics research deep dive](docs/RESEARCH_GRAPHICS_DEEP_DIVE.md)
- [Safety scope](docs/SAFETY.md)
- [Agent team charter](docs/AGENT_TEAM.md)

## Current limitations

- No real Xbox game image has yet been validated in this development workflow; format tests currently use synthetic fixtures.
- XGD2 partition offsets can vary; known offsets do not guarantee detection of every image, hybrid or unusual layout.
- XEX2 metadata parsing does not interpret encrypted/compressed PE payloads, import ordinals, or security-page hash structures.
- STFS/SVOD file-system and hash-table traversal is not implemented.
- XBE (original Xbox), XEX1 and other legacy/variant formats need separate verified parsers.
- A metadata report cannot determine whether a game can be ported. That requires executable analysis, asset and shader research, CPU/GPU behavior study, API mapping and validation on real target hardware.

## Safety and privacy

Orion-Core is designed for local, read-only analysis. It does not change registry settings, install drivers, run discovered executables, decrypt protected payloads, bypass access controls, or alter signatures. System diagnostics avoid collecting device serial numbers, MAC addresses, usernames, hostnames or personal files.

Only inspect game materials you are legally entitled to access.

## Windows standalone EXE

A standalone Windows x64 desktop build is produced by the **Windows EXE build** GitHub Actions workflow on pushes to `main` and by manual workflow dispatch. Open the repository's Actions tab, select the latest successful **Windows EXE build** run, and download the `Orion-Core-Windows-x64` artifact. Extract the ZIP and launch `Orion-Core.exe`.

The executable is a one-file PyInstaller build and does not require a separate Python installation. Windows may show its normal SmartScreen warning for an unsigned, self-built executable. The native Direct3D 12 probe is a separate optional C++ program and is not bundled into this Python GUI executable.
