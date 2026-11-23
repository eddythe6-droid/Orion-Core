# Graphics portability baseline

**Status:** initial research notes  
**Checked:** 2026-11-23  
**Evidence scope:** public Microsoft documentation; no game-specific binaries or assets examined.

## Confirmed platform facts

- Microsoft documents D3D12.x as the graphics API family for Xbox GDK titles; Xbox-specific extensions are part of that target.
- Microsoft's GDK overview states that Windows PC supports both D3D11 and D3D12, while Xbox GDK supports D3D12.x rather than D3D11.x.
- Microsoft's PC Direct3D 12 guide describes the PC API as targeting D3D12-compatible PC GPUs.
- Microsoft distinguishes stock public Direct3D APIs in the Windows SDK from device-specific graphics extensions in the Xbox GDK.

## Engineering consequences for a hypothetical PC adaptation

1. Treat the Xbox graphics backend and Windows PC graphics backend as related but distinct contracts.
2. Do not assume Xbox-specific interfaces, memory guarantees, queue behavior, or extension entry points are available on PC.
3. Create a capability model driven by runtime queries and explicit evidence. An absent capability must remain unknown/unsupported, not be guessed.
4. Keep graphics API selection separate from feature availability. "D3D12 device created" does not prove support for every optional feature.
5. Any future compatibility layer must be validated against public API documentation and synthetic test workloads, not proprietary game code.

## Unknowns

- Which graphics API, feature levels, extensions, shader model, render graph, or vendor-specific features GTA VI uses.
- Whether any particular Xbox graphics workload maps directly to PC without redesign.
- Required GPU memory, bandwidth, frame pacing, ray tracing, upscaling, or shader compilation strategy.

## Sources

- [Microsoft GDK overview](https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction?view=gdk-2604)
- [Windows graphics development overview](https://learn.microsoft.com/en-us/windows/apps/develop/graphics)
- [GDK Direct3D 12 programming guide](https://learn.microsoft.com/en-us/gaming/gdk/docs/gdk-dev/pc-dev/tutorials/pc-e2e-guide/directx-12-programming-guide?view=gdk-2604)
- [SDK and tools requirements](https://learn.microsoft.com/en-us/gaming/gdk/docs/gdk-dev/get-started/overviews/sdk-and-tools?view=gdk-2604)
