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

Per adapter, the report includes adapter name and vendor/device numeric IDs, dedicated video-memory capacity, D3D12 device creation, highest queried feature level, highest accepted shader model, resource binding tier, Options1 wave/compute fields, RGBA8 format support bitmasks, Options5 ray-tracing tier, Options7 mesh-shader and sampler-feedback tiers, a direct-queue/fence smoke test, and an upload-to-default-heap copy test with a transition barrier, readback, and byte-for-byte verification.

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


## Importing a probe report into Orion-Core

After copying the JSON output to a file, validate and normalize it with the Python package:

```powershell
python -m orion_core --gpu-probe-json .\\gpu-report.json
```

The importer checks the report schema and required adapter fields, then emits a comparison-friendly summary. It preserves unknown optional feature values and explicitly states that a valid hardware probe report does not establish game compatibility. The importer does not execute the native probe itself.


## Compare two GPU reports

Capture one JSON report per adapter/PC, then run:

```powershell
python -m orion_core --compare-gpus .\\gpu-a.json .\\gpu-b.json
```

Each input must contain exactly one hardware D3D12 adapter. The comparison orders known feature/tier values, compares reported boolean capabilities, and reports raw RGBA8 support-mask bit differences. Explicit `not_supported` is treated as a known lower tier; `unknown` remains unknown. The masks are not decoded into usage claims, and no performance or game-compatibility conclusion is produced.


## GPU memory budget snapshot

The native probe also attempts DXGI `IDXGIAdapter3::QueryVideoMemoryInfo` for the local and non-local memory segments. It records the current budget, current usage, and available-for-reservation value, along with a per-pool query flag. These are dynamic OS/driver budget values, not the board's physical VRAM capacity. Non-local memory refers to system-memory budget available to the GPU, not dedicated VRAM.

Analyze the snapshot with:

```powershell
python -m orion_core --gpu-memory-json .\\gpu-report.json
```

The report classifies usage against the reported budget (low <70%, moderate 70–<90%, high 90–100%, over-budget >100%). Missing or zero budgets remain unknown. The deterministic Python allocation pool is a simulation only; it does not allocate GPU memory or reproduce driver eviction.


The probe also attempts a native binding smoke test per hardware adapter. It
creates an empty root signature and shader-visible CBV/SRV/UAV and sampler
descriptor heaps, and reports creation outcomes plus descriptor increments.
These checks do **not** populate descriptors, bind heaps/root signatures to a
command list, create a pipeline state object, compile shaders, or execute a
draw/dispatch. A successful result therefore confirms object creation only.


## Native HLSL / PSO / draw smoke test

The probe also attempts a small off-screen rendering test per D3D12 hardware
adapter. It compiles minimal shader-model 5.0 HLSL vertex and pixel shaders
using the Windows SDK D3DCompiler, creates an empty root signature and a
graphics PSO, renders a triangle into a 64×64 RGBA8 render target, copies the
texture to a readback buffer, and verifies a center pixel against the expected
opaque-red output. The JSON records shader compilation, root-signature
creation, PSO creation, draw submission, overall verification, and a diagnostic
note.

This is a narrow driver/runtime smoke test, not a benchmark or full feature
conformance suite. It uses the legacy D3DCompiler shader compiler and shader
model 5.0 for broad Windows SDK availability; it does not validate DXIL,
Shader Model 6.x, Xbox-specific shader behavior, presentation/swap chains,
depth/stencil, blending variants, or game workloads. A reported draw submission
means the command list was recorded and submitted; only the overall successful
readback flag confirms the expected pixel was observed.
