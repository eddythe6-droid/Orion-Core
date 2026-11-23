# Native Windows D3D12 Probe

The C++ utility in `native/d3d12_probe` performs read-only capability queries against installed Windows graphics adapters.

## Build

Requirements: Windows 10/11, Visual Studio 2022 C++ build tools, Windows SDK, and CMake 3.24+.

From the repository root in a Visual Studio Developer PowerShell:

```powershell
cmake -S native/d3d12_probe -B build/d3d12-probe -A x64
cmake --build build/d3d12-probe --config Release
.\build\d3d12-probe\Release\orion-d3d12-probe.exe --json
```

By default, software adapters are excluded. Add `--include-software` to include WARP/software adapters in enumeration.

## Collected fields

- Adapter description, vendor/device IDs, and dedicated video-memory capacity reported by DXGI.
- Whether a D3D12 device can be created at feature level 11_0.
- Maximum reported feature level from the probe's request list.
- Highest shader model accepted by the installed SDK/driver query sequence.
- Resource binding tier.
- A minimal direct command-queue/fence signal-and-wait check.

The output is JSON with schema version 1. A failed optional feature query is reported as `unknown`, not inferred from the GPU model.

## Boundaries

This tool queries the local Windows D3D12 driver. It does not query Xbox D3D12.x, does not emulate Game OS, does not benchmark rendering performance, and cannot establish whether a particular game can be ported or run. The reported dedicated-memory figure is an adapter property, not the current available VRAM budget.

The probe is read-only: it creates temporary in-process D3D12 objects and a synchronization event, but does not write configuration, install drivers, change registry values, or persist files. It does not collect serial numbers or adapter LUIDs.

## CI interpretation

The Windows workflow compiles the native program. A hosted CI build does not prove that a physical GPU probe ran. Runtime validation requires execution on a Windows PC with a supported D3D12 adapter.
