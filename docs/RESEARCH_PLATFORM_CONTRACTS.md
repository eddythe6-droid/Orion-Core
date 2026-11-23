# Platform research: Xbox GDK ↔ Windows PC

**Status:** initial research baseline  
**Checked:** 2026-11-23  
**Scope:** public Microsoft documentation only. This is a platform study, not evidence about GTA VI internals.

## Executive result

A title built for Xbox and a Windows PC can share substantial game code, but they do not run against identical operating-system contracts. Microsoft's GDK deliberately defines a common subset of Win32 gaming APIs and a separate Gaming Runtime. Xbox also has a dedicated Game OS and platform-specific graphics/audio extensions. Therefore, a PC port is not safely modelled as "replace the executable and launch it": each dependency must be classified as common, PC-only, Xbox-only, or unknown, then mapped to a supported PC implementation.

## Evidence matrix

| Area | Xbox GDK / Game OS | Windows PC | Porting implication | Evidence status |
|---|---|---|---|---|
| Core OS API | GDK's `WINAPI_FAMILY_GAMES` subset is the intended portable core | PC titles may use the wider desktop API family | Audit every OS call; do not assume arbitrary desktop Win32 calls exist on Xbox or vice versa | Confirmed by Microsoft |
| Graphics | D3D12.x with Xbox-specific extensions | D3D11 and D3D12 are supported; PC D3D12 uses stock public API | Keep platform graphics backend boundaries explicit; Xbox-specific extensions cannot be assumed available on PC | Confirmed by Microsoft |
| Runtime/services | Gaming Runtime includes packaging, installation management, connected storage, accessibility and commerce-related APIs | Gaming Runtime is separately serviceable on PC; PC packaged titles may depend on it | Runtime services need a PC deployment and availability plan; do not treat them as built into Windows universally | Confirmed by Microsoft |
| File I/O/network | Common subset includes Win32 file I/O and WinSock2 | Windows desktop exposes broader OS APIs | Identify assumptions about paths, package layout, permissions, and network behavior; common API does not imply identical storage layout | Common APIs confirmed; title-specific behavior unknown |
| Input | XInput and GameInput are documented options | Both are available in the GDK common model | Build an input abstraction and validate device coverage on target PC hardware | Confirmed at API-family level |
| Audio | XAudio2 with Xbox extensions; Xbox-specific audio capabilities exist | XAudio2, WASAPI and spatial audio APIs are listed for PC | Separate device/format/mix assumptions from the game-facing audio interface | Confirmed by Microsoft |
| Packaging | Xbox package/deployment model and Game OS lifecycle | PC desktop template produces standalone executable; Gaming Runtime / MSIXVC paths are distinct choices | Packaging, activation, save location and update model must be researched independently | Confirmed by Microsoft |
| Memory/resources | Game OS provides explicit resource guarantees for supported title configurations | PC hardware/driver/resource availability varies by device | PC implementation must query and budget resources dynamically; Xbox guarantees cannot be copied as PC assumptions | Confirmed by Microsoft |

## Important distinctions

1. **GDK is not the same thing as the Windows SDK.** Microsoft's documentation describes the Windows SDK as exposing the public Win32 gaming API family and stock public graphics/audio APIs; the GDK adds gaming-focused runtime components, tools, and extensions.
2. **A shared codebase is possible, not automatic binary compatibility.** Microsoft explicitly describes projects targeting PC, Xbox, or both from a common codebase, with platform-specific capabilities where needed.
3. **Xbox D3D12.x is not simply the PC D3D12 runtime.** Microsoft identifies Xbox-specific D3D12.x extensions. The public PC Direct3D 12 programming guide describes the PC API separately.
4. **No GTA VI implementation details have been established.** This document does not claim the game uses any particular GDK API, renderer, package format, or engine subsystem.

## Proposed Orion-Core representation

Represent each discovered dependency as a claim with:
- subsystem and API/symbol name;
- target platform(s): Xbox, Windows PC, both, or unknown;
- classification: common / PC-only / Xbox-only / extension / unknown;
- required runtime or SDK;
- evidence URL, page title, checked date, and short supporting excerpt;
- confidence and unresolved questions;
- proposed PC equivalent or adapter, explicitly marked as a proposal until tested.

## Initial work queue

- [x] Build a machine-readable schema for platform claims and evidence.
- [x] Add a capability comparison model where missing evidence remains `unknown`.
- [x] Add test fixtures for common, PC-only, Xbox-only and unknown claims; reject invalid enum values at runtime.
- [ ] Research file/package lifecycle, save data, input, audio and graphics independently.
- [ ] Do not infer GTA VI usage from platform documentation alone.

## Sources (official Microsoft documentation)

- [What is the Microsoft Game Development Kit?](https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction?view=gdk-2604)
- [SDK and tools requirements](https://learn.microsoft.com/en-us/gaming/gdk/docs/gdk-dev/get-started/overviews/sdk-and-tools?view=gdk-2604)
- [Developing a new title with the GDK in Visual Studio](https://learn.microsoft.com/en-us/gaming/gdk/docs/gdk-dev/get-started/overviews/developing-new-titles-on-gamecore?view=gdk-2604)
- [Direct3D 12 programming guide](https://learn.microsoft.com/en-us/gaming/gdk/docs/gdk-dev/pc-dev/tutorials/pc-e2e-guide/directx-12-programming-guide?view=gdk-2604)
- [Development PC hardware and OS requirements](https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/get-started/overviews/set-up-dev-pc?view=gdk-2604)


## Input and save-data details

- **GameInput:** Microsoft documents GameInput for both Xbox and Windows. The API headers/library can be shared through the Microsoft.GameInput NuGet package, but runtime deployment is not identical: PC requires the redistributable or a supported sideloaded runtime, while Xbox includes a runtime in Game OS. The API versions available at runtime depend on the GDK release and runtime selected. See [GameInput FAQ](https://learn.microsoft.com/en-us/gaming/gdk/docs/features/common/input/overviews/input-faq?view=gdk-2604) and [GameInput on Xbox](https://learn.microsoft.com/en-us/xbox/gdk/docs/features/common/input/overviews/input-xbox?view=gdk-2610).
- **Game saves:** The GDK Game Saves developer guide lists XGameSave for PC and Xbox. It also documents endpoint-specific user lifecycle behavior: under the Simple User Model, PC terminates the game when the default user signs out, while console suspends it. Therefore, a shared API does not mean identical lifecycle assumptions. See [Game Saves developer guide](https://learn.microsoft.com/en-us/gaming/gdk/docs/features/common/game-save/game-saves-developer-guide?view=gdk-2604).
- **File I/O:** Win32 File I/O belongs to the common GDK programming model. However, paths, package layout, permissions, save-data ownership and synchronization remain separate audit items. See [What is the Microsoft GDK?](https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction?view=gdk-2604).

These claims describe public platform contracts only. They do not establish that a particular game uses these APIs.
