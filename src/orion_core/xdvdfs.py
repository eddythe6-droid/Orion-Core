"""Read-only XDVDFS/XISO volume and directory-table inspector."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

SECTOR_SIZE = 2048
VOLUME_MAGIC = b"MICROSOFT*XBOX*MEDIA"
MAX_DIRECTORY_DEPTH = 32
MAX_ENTRIES = 100_000
MAX_NAME_BYTES = 255


class XDVDFSError(ValueError):
    """Malformed or unsupported XDVDFS image."""


def _u32(data: bytes) -> int:
    if len(data) != 4:
        raise XDVDFSError("truncated 32-bit field")
    return struct.unpack("<I", data)[0]


def inspect_xdvdfs(path: str | Path, *, max_entries: int = MAX_ENTRIES) -> dict[str, Any]:
    """Inspect standard sector-32 or rebuilt sector-0 XDVDFS images.

    Sector references are interpreted relative to the detected XDVDFS volume
    base. No file payloads are read, extracted, mounted, or executed.
    """
    image = Path(path)
    if max_entries < 1:
        raise XDVDFSError("max_entries must be positive")
    try:
        image_size = image.stat().st_size
        with image.open("rb") as stream:
            volume_base = None
            descriptor_sector = None
            descriptor = None
            # Standard XISO has descriptor at base + sector 32; rebuilt images
            # may place the descriptor at byte zero.
            for base, sector in ((0, 32), (0, 0)):
                offset = base + sector * SECTOR_SIZE
                if offset + SECTOR_SIZE > image_size:
                    continue
                stream.seek(offset)
                candidate = stream.read(SECTOR_SIZE)
                if (len(candidate) == SECTOR_SIZE
                        and candidate[:20] == VOLUME_MAGIC
                        and candidate[0x7EC:0x800] == VOLUME_MAGIC):
                    volume_base, descriptor_sector, descriptor = base, sector, candidate
                    break
            if descriptor is None:
                raise XDVDFSError("XDVDFS volume descriptor not found at sector 32 or sector 0")

            root_sector = _u32(descriptor[0x14:0x18])
            root_size = _u32(descriptor[0x18:0x1C])
            timestamp = struct.unpack("<Q", descriptor[0x1C:0x24])[0]
            entries: list[dict[str, Any]] = []
            warnings: list[str] = []
            visited_directories: set[tuple[int, int]] = set()

            def read_directory(start_sector: int, table_size: int, prefix: str, depth: int) -> None:
                if depth > MAX_DIRECTORY_DEPTH:
                    warnings.append(f"{prefix or '/'}: directory depth limit reached")
                    return
                if start_sector == 0 and table_size == 0:
                    return
                key = (start_sector, table_size)
                if key in visited_directories:
                    warnings.append(f"{prefix or '/'}: directory cycle/reference skipped")
                    return
                visited_directories.add(key)
                table_offset = volume_base + start_sector * SECTOR_SIZE
                if table_size <= 0 or table_offset > image_size or table_size > image_size - table_offset:
                    warnings.append(f"{prefix or '/'}: directory table outside image")
                    return
                stream.seek(table_offset)
                table = stream.read(table_size)
                if len(table) != table_size:
                    warnings.append(f"{prefix or '/'}: truncated directory table")
                    return

                visited_nodes: set[int] = set()

                def visit(node_offset: int) -> None:
                    if node_offset == 0xFFFFFFFF:
                        return
                    if node_offset in visited_nodes:
                        warnings.append(f"{prefix or '/'}: directory-tree cycle/reference skipped")
                        return
                    if node_offset < 0 or node_offset + 14 > len(table):
                        warnings.append(f"{prefix or '/'}: directory-tree pointer outside table")
                        return
                    visited_nodes.add(node_offset)
                    left_units, right_units, data_sector, data_size = struct.unpack_from("<HHII", table, node_offset)
                    attributes = table[node_offset + 12]
                    name_length = table[node_offset + 13]
                    record_end = node_offset + 14 + name_length
                    if name_length == 0 or name_length > MAX_NAME_BYTES or record_end > len(table):
                        warnings.append(f"{prefix or '/'}: invalid directory entry name at {node_offset}")
                        return
                    name_bytes = table[node_offset + 14:record_end]
                    name = name_bytes.decode("ascii", errors="replace")
                    is_directory = bool(attributes & 0x10)
                    full_path = f"{prefix}/{name}" if prefix else name
                    if len(entries) >= max_entries:
                        raise XDVDFSError(f"entry limit reached ({max_entries})")
                    data_offset = volume_base + data_sector * SECTOR_SIZE
                    data_in_bounds = (data_sector == 0 and data_size == 0) or (
                        data_offset <= image_size and data_size <= image_size - data_offset
                    )
                    if not data_in_bounds:
                        warnings.append(f"{full_path}: data extent outside image")
                    entries.append({
                        "path": full_path,
                        "size_bytes": data_size,
                        "extent_sector": data_sector,
                        "directory": is_directory,
                        "attributes": attributes,
                        "read_only": bool(attributes & 0x01),
                        "hidden": bool(attributes & 0x02),
                        "system": bool(attributes & 0x04),
                        "archive": bool(attributes & 0x20),
                        "extent_in_bounds": data_in_bounds,
                    })
                    if is_directory and data_sector and data_size:
                        read_directory(data_sector, data_size, full_path, depth + 1)
                    # Child offsets are stored in DWORD units relative to this table.
                    if left_units:
                        visit(left_units * 4)
                    if right_units:
                        visit(right_units * 4)

                if table:
                    visit(0)

            if root_sector or root_size:
                read_directory(root_sector, root_size, "", 0)
            elif root_sector != 0 or root_size != 0:
                warnings.append("empty root directory has inconsistent sector/size fields")
    except OSError as exc:
        raise XDVDFSError(f"cannot read XDVDFS image: {type(exc).__name__}: {exc}") from exc

    entries.sort(key=lambda item: item["path"].casefold())
    return {
        "format": "XDVDFS",
        "volume_base_offset": volume_base,
        "descriptor_sector": descriptor_sector,
        "sector_size": SECTOR_SIZE,
        "root_directory_sector": root_sector,
        "root_directory_size_bytes": root_size,
        "creation_filetime_raw": timestamp,
        "entries_count": len(entries),
        "entries": entries,
        "warnings": warnings,
        "read_only": True,
        "extraction_performed": False,
        "filesystem_mount_performed": False,
    }
