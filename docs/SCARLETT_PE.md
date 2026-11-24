# Xbox Series / Scarlett executable candidate inspection

## Purpose

Xbox Series X|S GDK executables use the PE32+ x86-64 executable format. Orion-Core now has a separate Scarlett candidate assessment layered on the bounded PE parser. It is intentionally separate from the Xbox 360 XEX2 parser.

Microsoft's GDK documentation distinguishes console XVC packages from PC MSIXVC packages. Microsoft also documents the `xbdepends` sample, which analyzes EXE/DLL import modules and classifies Xbox/Scarlett dependencies. This supports using PE import-module inventory as an early diagnostic, not as a complete compatibility test.

## Current implementation

- Parse PE headers, architecture, sections, imported DLL names, and bounded imported function names/ordinals and delay-load DLL descriptors using the PE analyzer.
- Report x86-64 PE shape as a necessary architecture clue.
- Flag selected GDK/Xbox module names such as `d3d12_xs.dll`, `xgameruntime.dll`, `xgameplatform.dll`, `xmem.dll` and `xma2dsp.dll`.
- Preserve the underlying PE report.
- Label all import matches as hints; a name alone does not authenticate a game or establish that it targets Scarlett.
- Never execute, decrypt, unpack or patch the executable.

## Important limitations

The import-name list is deliberately small and must be expanded only from reliable GDK documentation, Microsoft samples or independently inspected authorized binaries. Delay-load DLL descriptors are inventoried (RVA- and VA-based forms); delay-load function thunks are not decoded. API sets, forwarded exports, static linking and runtime-loaded modules are not fully represented. Named imports and ordinal references are listed statically; ordinal targets are not resolved to export names. The parser does not validate package identity/configuration.

A PE32+ x86-64 file is not automatically an Xbox executable. Likewise, a GDK-looking import name does not prove that a file is an authentic Rockstar build. Authenticity and provenance require independent evidence.

## Why this helps port research

Import modules reveal which platform subsystems need compatibility work. For example, a `d3d12_xs.dll` dependency points toward Xbox-specific graphics interfaces; runtime, memory, audio and platform modules identify other likely API families. These are investigation leads, not proof that replacing a DLL or translating one API is sufficient.

## References

- [Microsoft: GDK packaging overview](https://learn.microsoft.com/en-us/gaming/gdk/docs/features/common/packaging/overviews/packaging?view=gdk-2610)
- [Microsoft: xbdepends sample](https://learn.microsoft.com/en-us/samples/microsoft/xbox-gdk-samples/xbdepends/)
- [Microsoft: PE format](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)
