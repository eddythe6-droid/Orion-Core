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


## Expanded executable evidence (Orion-Core research build)

The PE report now also records:

- PE, COFF, optional-header and section-table file offsets.
- Linker version, section/file alignment, image/header sizes, checksum field and DLL-characteristic flags.
- All available data-directory entries with their address interpretation. The Security directory is explicitly represented as a **file offset**, not an RVA.
- Section characteristics (code/data, read/write/execute), raw-range validity and overlap/out-of-file warnings.
- Entry-point RVA and its file offset when it can be mapped safely.
- Trailing bytes after mapped section/header data. This is only a boundary observation and may include a certificate table or other appended data.
- Bounded \`WIN_CERTIFICATE\` record framing: offset, length, revision and certificate type.

The certificate table parser does **not** decode PKCS#7 content, validate the Authenticode digest, build a trust chain, or identify a trusted publisher. A present certificate table is not proof of a valid signature or authentic Rockstar provenance. The report explicitly keeps all verification booleans false.

Scarlett/GDK dependency evidence now includes both normal-import and delay-load DLL modules. Where bounded normal-import symbols are available, the report includes their names/ordinals for the hinted Xbox modules. Delay-load function thunks are still not decoded.

The Game Inspector can optionally compute a full streaming SHA-256 for PE, XEX2 and XContent/STFS candidate files, including files larger than 64 MiB. This option is off by default and can take a long time for very large files. The separate general hashing option remains bounded to files no larger than 64 MiB. Neither option extracts or executes the file.

These additions improve the inventory of evidence; they do not expand the parser into a full GDK loader, XVC package parser, binary validator, or compatibility emulator.
