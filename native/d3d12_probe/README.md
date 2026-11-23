# Orion-Core native D3D12 probe

## Purpose

A read-only Windows utility that enumerates DXGI adapters and queries public Windows D3D12 runtime capabilities. It is a diagnostic input for Orion-Core research, not an Xbox emulator, game converter, benchmark, or compatibility guarantee.

## Build

Requirements: Windows 10/11 SDK with D3D12 headers, Visual Studio C++ build tools, and CMake 3.24 or newer.

From the repository root:

```powershell
cmake -S native/d3d12_probe -B build/d3d12-probe -A x64
cmake --build build/d3d12-probe --config Release
```

Executable:

```powershell
.\build\d3d12-probe\Release\orion-d3d12-probe.exe --json
```

Include software adapters only when specifically useful for diagnosis:

```powershell
.\build\d3d12-probe\Release\orion-d3d12-probe.exe --json --include-software
```

The process prints one JSON object to standard output. Exit code 0 means at least one hardware adapter successfully created a D3D12 device; exit code 3 means no hardware D3D12 adapter was successfully created; exit code 1 indicates an early DXGI setup failure; exit code 2 indicates invalid command-line arguments.

## Reported data

Per adapter, the report includes adapter name and vendor/device numeric IDs, dedicated video-memory capacity, D3D12 device creation, highest queried feature level, highest accepted shader model, resource binding tier, Options1 wave/compute fields, RGBA8 format support bitmasks, Options5 ray-tracing tier, Options7 mesh-shader and sampler-feedback tiers, and a direct-queue/fence smoke test.

Query availability is reported separately for optional feature structures. Unknown values must not be interpreted as unsupported. Format support values are raw D3D12 bitmasks and must be decoded using the Windows SDK definitions corresponding to the probe build.

## Interpretation cautions

- Adapter VRAM capacity is not the current process video-memory budget.
- A successful queue/fence smoke test does not validate command-list execution, presentation, shader compilation, or rendering correctness.
- A feature tier is a runtime/driver capability report, not a performance result.
- A D3D12 feature query does not establish support for Xbox D3D12.x extensions.
- This tool does not inspect game binaries, extract assets, bypass DRM, or change drivers, registry settings, files, or system configuration.
- Do not publish raw diagnostic output without reviewing it first. Orion-Core avoids collecting serial numbers and filesystem paths, but adapter names and numeric IDs are still hardware metadata.

## Validation status

The GitHub Actions Windows job compiles the executable. That is compile validation only. Runtime validation requires executing the binary on a physical Windows PC with a D3D12 adapter and reviewing the resulting JSON.
