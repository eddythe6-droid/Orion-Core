# Orion Game Inspector

The first game-file workflow is a conservative, read-only inventory tool.

## What it does
- Recursively inventories regular files in a directory without following symbolic links.
- Reads only a short header from regular files to identify a small set of well-known signatures.
- Lists members of ZIP-compatible archives using metadata only; it never extracts members.
- Optionally computes SHA-256 for regular files up to 64 MiB.
- Writes a machine-readable JSON report.
- Parses core PE headers for MZ candidates: architecture, PE32/PE32+, image base, entry point, subsystem, sections, and imported DLL names when the import table is safely mappable.

## What it does not do
- It does not execute files, unpack proprietary containers, decrypt content, bypass DRM, or infer game compatibility.
- Extension labels are hints, not proof of a file's internal format.
- An MZ signature is only a PE candidate. The parser validates core PE structures and extracts limited metadata; it is not a complete PE/COFF validator and does not decode imports by ordinal or inspect resources, relocations, TLS, load configuration, or executable code.
- Xbox-specific formats are recognized only by basic signatures or filename extensions. A detected label is not proof that a valid Xbox executable/package was parsed.

## CLI
PowerShell examples:
- python -m orion_core --inspect-game-path "D:\GameFiles" --inspect-output ".\game-inventory.json"
- python -m orion_core --inspect-game-path ".\disc.zip" --inspect-hash-files

Archive member listing is metadata-only. The tool applies file/member limits to avoid unbounded scans.
