# Curated platform capability catalogue

**Checked:** 2026-11-23  
**Source policy:** public Microsoft documentation only.

The Python catalogue in `src/orion_core/platform_catalog.py` currently records six documented platform facts. Each entry carries a stable claim ID, subsystem, platform classification, confidence, checked date, and source URL.

## Current findings

| Claim ID | Subsystem | Documented fact | Portability interpretation |
|---|---|---|---|
| GDK-API-001 | OS API | GDK defines a common Win32 gaming API subset for PC and Xbox | Common API surface is a starting point; audit behavior and platform-specific assumptions |
| GDK-GFX-001 | Graphics | Xbox GDK uses D3D12.x; D3D11.x is not supported on Xbox | Xbox-specific graphics contract cannot be assumed on PC |
| GDK-GFX-002 | Graphics | PC and Xbox builds use stock D3D12 and D3D12.x respectively | Keep backend/build boundaries explicit |
| GDK-RUNTIME-001 | Runtime | Gaming Runtime is separately serviceable on PC and part of Game OS on Xbox | Validate PC runtime deployment and dependency availability |
| GDK-MEM-001 | Memory/resources | Xbox Game OS documents explicit CPU/GPU/memory/I/O guarantees | Do not carry console resource guarantees over to heterogeneous PC hardware |
| GDK-PROJECT-001 | Build system | PC and Xbox targets can share a codebase with platform-specific configurations | Shared codebase does not mean one binary or no porting work |

## What this does not establish

- It does not show that GTA VI uses GDK, D3D12.x, MSIXVC, or any particular API.
- It does not establish the game's renderer, engine, memory budget, asset formats, or platform-specific code.
- It is not a reverse-engineering result and does not rely on leaked or proprietary materials.

## Official sources

- [Microsoft GDK overview](https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction?view=gdk-2604)
- [Developing a new title with the GDK in Visual Studio](https://learn.microsoft.com/en-us/gaming/gdk/docs/gdk-dev/get-started/overviews/developing-new-titles-on-gamecore?view=gdk-2604)
- [Microsoft GDK documentation](https://learn.microsoft.com/en-us/gaming/gdk/?view=gdk-2604)
- [Microsoft public GDK repository](https://github.com/microsoft/GDK)
