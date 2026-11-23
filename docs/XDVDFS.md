# XDVDFS / XISO inspection

Orion-Core includes a bounded, read-only metadata parser for Xbox DVD File System (XDVDFS), commonly called XISO.

## Supported image layouts

The parser probes the standard volume descriptor at sector 32 relative to these game-partition bases:

| Layout | Partition base | Description |
|---|---:|---|
| Bare XISO | `0x00000000` | Extracted game partition |
| XGD2 | `0x0FD90000` | Common full-disc dump layout |
| XGD3 | `0x02080000` | Common full-disc dump layout |
| XGD1 | `0x18300000` | Original Xbox full-disc dump layout |

It also accepts rebuilt XISO images with the descriptor at byte offset zero. The selected layout and partition base are recorded in the report.

The parser validates the 20-byte `MICROSOFT*XBOX*MEDIA` marker at both the beginning and end of the 2048-byte descriptor. It reads the little-endian root directory sector and size, raw creation FILETIME, and the directory tree.

## Directory metadata

Each directory table is treated as a binary tree. Entries contain left/right child offsets in DWORD units, a data start sector, a 32-bit size, attributes, and a single-byte filename. The directory attribute bit is `0x10`. File payloads are not read.

The report includes paths, sizes, extent sectors, attribute bits, and whether the referenced data extent fits within the image. Directory and tree cycles, out-of-range pointers, malformed names, depth, and entry counts are bounded or reported as warnings.

## Current limitations

- XGD2 video-partition offsets can vary between discs; the fixed-offset probes are common-layout detection, not exhaustive identification. XGD2 hybrid and dual-layer variants are not yet detected.
- STFS/SVOD containers and split data-file sets are not parsed.
- No file extraction, mounting, decryption, signature processing, or execution is performed.
- A directory listing does not establish executable compatibility or prove that the image is complete.

## CLI

```powershell
python -m orion_core --inspect-game-path ".\\game.iso" --inspect-output ".\\game-inventory.json"
python -m orion_core --inspect-game-path ".\\game.xiso"
```

For ordinary ISO9660 images, Game Inspector falls back to its separate ISO9660 reader after XDVDFS detection fails.

## Research references

- Xbox-Linux, *Xbox DVD Filesystem Details* (2002): volume descriptor and directory-tree layout.
- XboxDevWiki, *XDVDFS*: volume descriptor and attribute bits.
- antangelo/xdvdfs: open-source XDVDFS metadata tooling.

These references describe format structures; they do not imply that all disc mastering and partition variants are implemented here.
