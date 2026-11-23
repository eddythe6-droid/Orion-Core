# Graphics deep dive: Windows PC D3D12 and Xbox boundaries

Checked: 2026-11-23  
Scope: public Microsoft documentation and a proposed synthetic test harness. This document makes no claim about GTA VI's private renderer, engine, assets, or platform implementation.

## Executive result

The public PC Direct3D 12 API exposes enough control to build a meaningful compatibility laboratory for command submission, synchronization, resource residency, descriptor binding, root signatures, pipeline state, and feature queries. That laboratory can validate Windows PC behavior and test our own adapter abstractions.

It cannot prove that an Xbox title uses the same queue topology, memory policy, descriptor layout, shader binaries, or undocumented D3D12.x extensions. The existing GDK catalogue treats Xbox D3D12.x as a distinct platform contract. No Xbox feature bit or private interface is guessed here.

## Subsystem comparison

| Area | Public Windows PC D3D12 contract | Xbox boundary / PC adapter strategy | Orion-Core test scope |
|---|---|---|---|
| GPU queues | Applications record command lists and submit them to command queues. Direct, compute and copy work can be synchronized with fences. | Do not assume identical queue counts, priorities, scheduling or hardware topology on Xbox. Use a backend-neutral queue model and implement the PC backend with public D3D12 queues/fences. | Verify FIFO submission per queue, fence signal/wait ordering, cross-queue dependencies and safe resource reuse only after completion. |
| Memory and residency | Applications manage heaps/resources, residency and a changing video-memory budget. Committed, placed and reserved resources have different allocation semantics. | Xbox Game OS has documented resource guarantees for supported configurations; Windows PCs are heterogeneous. Model budgets as runtime inputs, never fixed console constants. | Synthetic budget-pressure scenarios, allocation lifetime, eviction/residency transitions and ownership. Actual residency tests require a Windows D3D12 host. |
| Descriptors and binding | Descriptors describe resources; descriptor heaps store them; descriptor tables and root signatures define shader-visible binding. The application must not overwrite descriptors still referenced by in-flight GPU work. | The public PC model is useful, but does not prove a game's exact Xbox binding layout or use of D3D12.x extensions. | Validate descriptor ranges, heap capacity, generation/lifetime tracking, root slots and in-flight protection. |
| Shaders and PSO | D3D12 supports shader-model capability queries. Microsoft documents Shader Model 6 with DXIL/DXC as a modern path; exact support must be queried. PSOs combine shader and fixed-function state. | Do not assume shader model, DXIL version, compiler flags, bytecode compatibility or Xbox-specific extensions from the platform name. | Query PC feature support; validate metadata and pipeline compatibility using our own shaders. No proprietary shader extraction/conversion. |
| Feature support | Use `ID3D12Device::CheckFeatureSupport` for feature levels, shader model, format support and other capabilities. | Do not infer Xbox support from a PC query, or PC support from an Xbox-only statement. | Store queried capability snapshots with driver/runtime provenance and explicit unknown values. |

## Detailed findings

### 1. Queues and synchronization

D3D12 uses recorded command lists rather than an immediate context. Command queues submit work; fences provide explicit synchronization. The PC harness should represent dependencies as a graph rather than assume a single global GPU timeline. Resource barriers and queue/fence synchronization are separate concerns: barriers describe resource state/visibility transitions, while fences coordinate progress between timelines.

**Portable abstraction:** `QueueKind` (direct/compute/copy), `Submission`, `FencePoint`, and `ResourceDependency`. Keep platform-specific queue creation and capabilities behind a backend interface.

### 2. Memory, heaps and residency

On Windows, GPU accessibility requires resources to be resident. Budgets can fluctuate, and discrete and UMA adapters have different memory-pool characteristics. D3D12 exposes committed, placed and reserved resource patterns; they are not interchangeable. A synthetic model can exercise allocation policy and failure handling, but only a native Windows run can observe actual adapter budgets, residency calls, driver behavior and device-removal conditions.

**Portable abstraction:** report memory pools, budget, current usage, allocation kind and residency state as measured or unknown fields. Never substitute installed VRAM capacity for the current process budget.

### 3. Descriptors and root signatures

Descriptors are the binding unit for resources such as SRVs, UAVs, CBVs and samplers. Descriptor heaps contain them; descriptor tables reference ranges; root signatures define the binding contract expected by shaders and PSOs. Shader-visible descriptor contents must not be recycled while submitted GPU work can still reference them.

**Portable abstraction:** a descriptor allocator with explicit capacity, range ownership, frame/fence retirement and validation. The synthetic harness can detect premature reuse and out-of-range references without a GPU.

### 4. Shaders and pipeline state

PC D3D12 exposes shader model and feature-level queries. Shader Model 6 uses DXIL and the DXC compiler path documented by Microsoft; the exact available shader model must be queried from the adapter/runtime. Pipeline state objects combine shader stages with fixed-function state. A successful PC shader compile says nothing about an unknown Xbox shader binary or proprietary compilation pipeline.

**Portable abstraction:** record shader target, compiler identity/version, bytecode format, required features and PSO requirements. Unknown fields remain unknown; do not fabricate Xbox shader profiles.

### 5. Feature detection

The Windows backend should call `CheckFeatureSupport` and record actual results for feature level, shader model, format support, resource binding tier and optional features. Existing Orion-Core registry diagnostics are not a substitute for these runtime queries.

## Proposed synthetic harness

The first harness should be deterministic and hardware-independent:

1. Queue simulator: multiple queue timelines, monotonically increasing fence values, waits, and invalid early resource reuse.
2. Residency simulator: configurable memory pools/budgets, allocation classes, make-resident/evict transitions and budget pressure.
3. Descriptor allocator: heap capacity, table ranges, root signature slots, frame ownership and fence-based retirement.
4. Capability snapshot schema: adapter/driver/runtime identity, queried features, query timestamp, and explicit `unknown` for unqueried values.
5. Validation report: invariant pass/fail plus exact synthetic scenario; clearly label all generated data as synthetic.

Then, on a Windows PC with a supported D3D12 adapter, add a small native sample that queries real capabilities, creates one direct queue and fence, uploads a small buffer, binds a minimal shader resource and renders a simple test frame. This native stage has not yet been implemented or run.

## What this does and does not establish

**Established by public documentation:** the PC-side mechanisms listed above exist and can be tested using public D3D12 APIs.

**Engineering inference:** a backend-neutral model plus a PC D3D12 backend is a sound way to isolate platform-specific behavior and test our own synchronization/resource-management logic.

**Still unknown:** GTA VI's actual engine architecture, shader model, queue arrangement, memory layout, use of Xbox extensions, build configuration, and whether any private title dependency can be replaced. Public platform documentation alone cannot answer these questions.

## Sources

- Microsoft: [Work submission in Direct3D 12](https://learn.microsoft.com/en-us/windows/win32/direct3d12/command-queues-and-command-lists)
- Microsoft: [Residency](https://learn.microsoft.com/en-us/windows/win32/direct3d12/residency)
- Microsoft: [Resource Binding](https://learn.microsoft.com/en-us/windows/win32/direct3d12/resource-binding)
- Microsoft: [Resource binding overview](https://learn.microsoft.com/en-us/windows/win32/direct3d12/resource-binding-flow-of-control)
- Microsoft: [Hardware Feature Levels](https://learn.microsoft.com/en-us/windows/win32/direct3d12/hardware-feature-levels)
- Microsoft: [Porting from Direct3D 11 to Direct3D 12](https://learn.microsoft.com/en-us/windows/win32/direct3d12/porting-from-direct3d-11-to-direct3d-12)


## Native probe capability snapshot (implemented)

The Windows-only C++ probe now records additional public D3D12 queries per successfully created hardware device:

- `D3D12_FEATURE_D3D12_OPTIONS1`: wave-operation support, minimum/maximum wave lane count, total lane count, 64-bit shader integer operations, and expanded compute resource states.
- `D3D12_FEATURE_FORMAT_SUPPORT` for `DXGI_FORMAT_R8G8B8A8_UNORM`, preserving both support bitmasks.
- Query availability is emitted separately. Values are JSON `null` when the query fails; they are not silently converted to `false` or zero.

These are adapter/runtime observations, not a prediction of game compatibility. A format support bitmask must be decoded against the Windows SDK definitions used to build the probe. The probe does not yet test ray tracing, mesh shaders, sampler feedback, actual shader compilation, presentation, or sustained GPU workloads. CI compilation is not a substitute for running the executable on physical Windows hardware.


### Advanced optional graphics features (native query coverage)

The native Windows probe also queries `D3D12_FEATURE_D3D12_OPTIONS5` and `D3D12_FEATURE_D3D12_OPTIONS7`:

- Ray tracing tier (Options5).
- Mesh shader tier (Options7).
- Sampler feedback tier (Options7).

Each Options structure has its own `*_query_available` field. A tier is emitted as `unknown` if the corresponding query is unavailable or the returned enum is not recognized by the SDK used to compile the probe. `not_supported` is emitted only when the runtime explicitly returns the documented not-supported enum. This distinction prevents an older runtime from being mistaken for hardware that definitively lacks a feature.

These queries report D3D12 runtime/driver capability exposure. They do not test performance, validate a complete rendering path, prove that a particular game uses the feature, or establish compatibility with Xbox D3D12.x.


### Representative texture and render-target format queries (implemented)

The native probe now queries D3D12_FEATURE_FORMAT_SUPPORT for a small representative set:

- R8G8B8A8_UNORM and B8G8R8A8_UNORM — common 8-bit color formats.
- R16G16B16A16_FLOAT — higher-precision color/HDR-style data format.
- R32_FLOAT — scalar floating-point data.
- D32_FLOAT — depth format.
- BC1_UNORM and BC7_UNORM — block-compressed texture formats.

For each format the JSON report records query_available, support1, and support2. The importer validates the record shape, rejects negative/non-integer masks, and preserves null masks when a query is unavailable. These raw masks must be decoded using the matching Windows SDK definitions before making a specific usage claim; they are not themselves a verdict that a texture can be used in every pipeline role.
