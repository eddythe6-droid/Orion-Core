# Orion Game Inspector

The first game-file workflow is a conservative, read-only inventory tool.

## What it does
- Recursively inventories regular files in a directory without following symbolic links.
- Reads only a short header from regular files to identify a small set of well-known signatures.
- Lists members of ZIP-compatible archives using metadata only; it never extracts members.
- Detects and inventories XDVDFS/XISO volume descriptors and directory trees in common XGD1/XGD2/XGD3 partition layouts, bare XISO, and rebuilt sector-0 images; falls back to ISO9660 for ordinary `.iso` images. No mounting or extraction.
- Parses public XContent metadata from `CON `, `LIVE`, and `PIRS` package headers, including content type, title/media IDs, disc metadata, display strings, and STFS/SVOD descriptor type.
- Identifies a common Xbox 360 Games on Demand (GOD) sibling layout (`<ContentID>` plus `<ContentID>.data/DataNNNN`) using names and file sizes only.
- Optionally computes SHA-256 for regular files up to 64 MiB.
- Writes a machine-readable JSON report.
- Parses core PE headers for MZ candidates: architecture, PE32/PE32+, image base, entry point, subsystem, sections, imported DLL names, and bounded named/ordinal import symbols and delay-load DLL descriptors when tables are safely mappable.
- Adds a separate Xbox Series / Scarlett candidate assessment for x64 PE files using a small allowlist of GDK/Xbox import-module names. This is a heuristic only, not proof of platform identity or authenticity.

## What it does not do
- It does not execute files, unpack proprietary containers, decrypt content, bypass DRM, or infer game compatibility.
- Extension labels are hints, not proof of a file's internal format.
- An MZ signature is only a PE candidate. Scarlett import hints are also heuristic: x64 PE shape and DLL names do not authenticate a game or prove console provenance. The parser validates core PE structures and extracts limited metadata; it is not a complete PE/COFF validator and does not resolve ordinal imports to export names or decode delay-load function thunks; it also does not inspect resources, relocations, TLS, load configuration, or executable code.
- STFS inspection reads only the fixed public XContent metadata header. It does not validate RSA signatures or SHA-1 hash trees, parse the STFS file table, inspect SVOD hash tables, join DataNNNN payloads, or reconstruct a disc image. A `SVOD` descriptor is not itself proof of a complete GOD folder.
- GOD/SVOD directory recognition is a conservative name/layout heuristic; it reports observed sibling files and sizes only. No payload bytes are read.
- Xbox-specific formats not covered by a dedicated parser are recognized only by basic signatures or filename extensions. A detected label is not proof that a valid Xbox executable/package was parsed.

## CLI
PowerShell examples:
- python -m orion_core --inspect-game-path "D:\GameFiles" --inspect-output ".\game-inventory.json"
- python -m orion_core --inspect-game-path ".\disc.zip" --inspect-hash-files

Archive, ISO, STFS and GOD/SVOD inspection is metadata-only. XDVDFS supports known common XGD1/XGD2/XGD3 partition offsets and bare/rebuilt XISO; variable XGD2 offsets and hybrid layouts remain unsupported. A successful directory listing is metadata inspection, not proof that the game can run on Windows. The tool applies file/member limits to avoid unbounded scans.
