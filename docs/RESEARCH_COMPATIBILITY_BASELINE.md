# Windows compatibility research baseline

**Status:** initial research notes  
**Checked:** 2026-11-23  
**Scope:** documented GDK platform contracts, not GTA VI internals.

## Confirmed

- GDK's common programming model includes Win32 file I/O, WinSock2, XInput, and D3D12 (with D3D12.x on Xbox).
- The Gaming Runtime is a distinct component. On Windows PC it is delivered as a separately serviceable package; Xbox includes it as part of Game OS.
- Microsoft describes PC and Xbox GDK title templates separately. A PC desktop title uses the desktop API family and typical PC libraries; an Xbox title uses the games API family and the Xbox platform library.
- The PC GDK runtime requirements and packaging/deployment path need to be considered on the target PC, rather than assuming the console environment exists.

## Compatibility areas to investigate

| Area | Questions for a future compatibility adapter |
|---|---|
| Filesystem | How are install, writable data, save, cache and streamed-content paths selected on each platform? |
| Package lifecycle | What performs install, activation, updates, optional content and shutdown? |
| Saves | Which storage abstraction is used, and what is the PC equivalent and failure behavior? |
| Input | Which devices and controller APIs are required? How are hot-plug and focus loss handled? |
| Audio | Which APIs, formats, spatial features and device-change behaviors are required? |
| Networking | Which WinSock/WinHTTP facilities are used, and are there service/runtime dependencies? |
| Threads/synchronization | Which primitives are assumed, and are any platform-specific scheduling guarantees relied upon? |
| UI/windowing | Which activation, window, display, fullscreen and suspend/resume contracts are assumed? |

## Rule for this project

Do not implement speculative shims for APIs not evidenced by authorized source material. First create an evidence-backed dependency entry, then define a PC mapping, then test the mapping using a small synthetic program. Never bypass DRM, anti-cheat, licensing, encryption or access controls.

## Sources

- [What is the Microsoft Game Development Kit?](https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction?view=gdk-2604)
- [Developing a new title with the GDK in Visual Studio](https://learn.microsoft.com/en-us/gaming/gdk/docs/gdk-dev/get-started/overviews/developing-new-titles-on-gamecore?view=gdk-2604)
- [Development PC hardware and OS requirements](https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/get-started/overviews/set-up-dev-pc?view=gdk-2604)
