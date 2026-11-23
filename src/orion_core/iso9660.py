"""Read-only ISO9660 directory reader; no extraction or filesystem mounting."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

SECTOR_SIZE = 2048
MAX_DIRECTORY_DEPTH = 32
MAX_ENTRIES = 100_000


class ISO9660Error(ValueError):
    """Malformed or unsupported ISO9660 image."""


def _both16(data: bytes) -> int:
    if len(data) != 4:
        raise ISO9660Error("invalid both-endian 16-bit field")
    little, big = struct.unpack("<H", data[:2])[0], struct.unpack(">H", data[2:])[0]
    if little != big:
        raise ISO9660Error("ISO9660 endian copies disagree")
    return little


def _both32(data: bytes) -> int:
    if len(data) != 8:
        raise ISO9660Error("invalid both-endian 32-bit field")
    little, big = struct.unpack("<I", data[:4])[0], struct.unpack(">I", data[4:])[0]
    if little != big:
        raise ISO9660Error("ISO9660 endian copies disagree")
    return little


def inspect_iso9660(path: str | Path, *, max_entries: int = MAX_ENTRIES) -> dict[str, Any]:
    """Read the primary volume descriptor and enumerate directory records."""
    image = Path(path)
    if max_entries < 1:
        raise ISO9660Error("max_entries must be positive")
    try:
        size = image.stat().st_size
        with image.open("rb") as stream:
            pvd = None
            for sector in range(16, min(size // SECTOR_SIZE, 80)):
                stream.seek(sector * SECTOR_SIZE)
                descriptor = stream.read(SECTOR_SIZE)
                if len(descriptor) != SECTOR_SIZE:
                    break
                if descriptor[1:6] != b"CD001" or descriptor[6] != 1:
                    continue
                if descriptor[0] == 1:
                    pvd = descriptor
                    break
                if descriptor[0] == 255:
                    break
            if pvd is None:
                raise ISO9660Error("primary ISO9660 volume descriptor not found")

            volume_space = _both32(pvd[80:88])
            logical_block_size = _both16(pvd[128:132])
            if logical_block_size != SECTOR_SIZE:
                raise ISO9660Error(f"unsupported logical block size: {logical_block_size}")
            root_len = pvd[156]
            root = pvd[156:156 + root_len]
            if root_len < 34 or len(root) != root_len:
                raise ISO9660Error("invalid root directory record")
            root_extent = _both32(root[2:10])
            root_size = _both32(root[10:18])

            entries: list[dict[str, Any]] = []
            warnings: list[str] = []
            visited: set[tuple[int, int]] = set()

            def read_directory(extent: int, data_length: int, prefix: str, depth: int) -> None:
                if depth > MAX_DIRECTORY_DEPTH:
                    warnings.append(f"{prefix or '/'}: directory depth limit reached")
                    return
                key = (extent, data_length)
                if key in visited:
                    warnings.append(f"{prefix or '/'}: directory cycle/reference skipped")
                    return
                visited.add(key)
                offset = extent * SECTOR_SIZE
                if extent >= volume_space or data_length > size - offset:
                    warnings.append(f"{prefix or '/'}: directory extent outside image")
                    return
                stream.seek(offset)
                data = stream.read(data_length)
                pos = 0
                while pos < len(data):
                    record_len = data[pos]
                    if record_len == 0:
                        pos = ((pos // SECTOR_SIZE) + 1) * SECTOR_SIZE
                        continue
                    if record_len < 34 or pos + record_len > len(data):
                        warnings.append(f"{prefix or '/'}: malformed directory record at byte {pos}")
                        break
                    record = data[pos:pos + record_len]
                    name_len = record[32]
                    if 33 + name_len > record_len:
                        warnings.append(f"{prefix or '/'}: malformed identifier")
                        pos += record_len
                        continue
                    identifier = record[33:33 + name_len]
                    flags = record[25]
                    is_dir = bool(flags & 0x02)
                    if identifier not in (b"\x00", b"\x01"):
                        name = identifier.decode("ascii", errors="replace")
                        if ";" in name:
                            name = name.rsplit(";", 1)[0]
                        name = name.rstrip(".")
                        full = f"{prefix}/{name}" if prefix else name
                        file_extent = _both32(record[2:10])
                        file_size = _both32(record[10:18])
                        if len(entries) >= max_entries:
                            raise ISO9660Error(f"entry limit reached ({max_entries})")
                        entries.append({
                            "path": full,
                            "size_bytes": file_size,
                            "extent_sector": file_extent,
                            "directory": is_dir,
                            "interleaved": bool(record[26] or record[27]),
                            "recorded_time_raw": record[18:25].hex(),
                        })
                        if is_dir:
                            read_directory(file_extent, file_size, full, depth + 1)
                    pos += record_len

            read_directory(root_extent, root_size, "", 0)
    except OSError as exc:
        raise ISO9660Error(f"cannot read ISO image: {type(exc).__name__}: {exc}") from exc

    entries.sort(key=lambda item: item["path"].casefold())
    return {
        "format": "ISO9660",
        "volume_identifier": pvd[40:72].decode("ascii", errors="replace").strip(),
        "volume_space_sectors": volume_space,
        "logical_block_size": logical_block_size,
        "root_extent_sector": root_extent,
        "entries_count": len(entries),
        "entries": entries,
        "warnings": warnings,
        "read_only": True,
        "extraction_performed": False,
        "filesystem_mount_performed": False,
    }
