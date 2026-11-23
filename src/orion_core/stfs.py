"""Read-only Xbox 360 XContent/STFS header and SVOD layout inspector.

Only public, unencrypted header metadata and directory/file sizes are read.
No package signature verification, hash-table traversal, payload decoding,
extraction, decryption, or access-control circumvention is performed.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

MAGICS = {b"CON ": "CON", b"LIVE": "LIVE", b"PIRS": "PIRS"}
BASE_METADATA_END = 0x1720
CONTENT_TYPES = {
    0x00000001: "saved_game",
    0x00000002: "marketplace_content",
    0x00001000: "xbox_360_title",
    0x00007000: "games_on_demand",
    0x00010000: "profile",
    0x000B0000: "title_update",
}


class STFSError(ValueError):
    """Malformed or unsupported XContent/STFS header."""


def _be32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _be64(data: bytes, offset: int) -> int:
    return struct.unpack_from(">Q", data, offset)[0]


def _utf16be(data: bytes) -> str:
    try:
        return data.split(b"\\x00\\x00", 1)[0].decode("utf-16-be", errors="replace").rstrip("\\x00").strip()
    except Exception:
        return ""


def inspect_stfs(path: str | Path) -> dict[str, Any]:
    """Read the fixed XContent metadata fields from an STFS/SVOD header."""
    source = Path(path)
    try:
        with source.open("rb") as stream:
            header = stream.read(BASE_METADATA_END)
    except OSError as exc:
        raise STFSError(f"cannot read package header: {type(exc).__name__}: {exc}") from exc
    if len(header) < 4 or header[:4] not in MAGICS:
        raise STFSError("CON/LIVE/PIRS package signature not found")
    if len(header) < BASE_METADATA_END:
        raise STFSError("truncated XContent metadata header")
    magic = MAGICS[header[:4]]
    content_type = _be32(header, 0x344)
    metadata_version = _be32(header, 0x348)
    declared_size = _be64(header, 0x34C)
    volume_type = _be32(header, 0x3A9)
    if volume_type not in (0, 1):
        volume_name = "unknown"
    else:
        volume_name = "STFS" if volume_type == 0 else "SVOD"
    display_name = _utf16be(header[0x411:0x491])
    display_description = _utf16be(header[0xD11:0xD91])
    publisher = _utf16be(header[0x1611:0x1691])
    title_name = _utf16be(header[0x1691:0x1711])
    return {
        "format": "XContent",
        "container_format": volume_name,
        "signature_type": magic,
        "header_size_field": _be32(header, 0x340),
        "content_type": content_type,
        "content_type_name": CONTENT_TYPES.get(content_type, "unknown"),
        "metadata_version": metadata_version,
        "declared_content_size": declared_size,
        "media_id": _be32(header, 0x354),
        "title_id": _be32(header, 0x360),
        "platform": header[0x364],
        "executable_type": header[0x365],
        "disc_number": header[0x366],
        "disc_count": header[0x367],
        "data_file_count": _be32(header, 0x39D),
        "data_file_combined_size": _be64(header, 0x3A1),
        "display_name": display_name,
        "display_description": display_description,
        "publisher_name": publisher,
        "title_name": title_name,
        "signature_verified": False,
        "hash_tables_read": False,
        "payload_read": False,
        "extraction_performed": False,
        "decryption_or_drm_bypass": False,
        "metadata_only": True,
    }


def inspect_svod_directory(path: str | Path) -> dict[str, Any]:
    """Identify a GOD-style sibling header/.data directory using names and sizes only."""
    root = Path(path)
    if not root.is_dir():
        raise STFSError("SVOD directory inspection requires a directory")
    data_dirs = sorted(p for p in root.iterdir() if p.is_dir() and p.name.lower().endswith(".data"))
    candidates = []
    for data_dir in data_dirs:
        package_name = data_dir.name[:-5]
        header_path = root / package_name
        if not header_path.is_file():
            continue
        try:
            metadata = inspect_stfs(header_path)
        except STFSError:
            continue
        files = sorted(p for p in data_dir.iterdir() if p.is_file() and p.name.lower().startswith("data"))
        candidates.append({
            "header_file": package_name,
            "data_directory": data_dir.name,
            "package_metadata": metadata,
            "data_files": [{"name": p.name, "size_bytes": p.stat().st_size} for p in files],
            "data_file_count_observed": len(files),
            "layout_name_pattern": all(p.name.lower() == f"data{i:04d}" for i, p in enumerate(files)),
            "payload_parsed": False,
        })
    return {
        "format": "Xbox 360 GOD/SVOD directory",
        "containers": candidates,
        "metadata_only": True,
        "payload_reassembled": False,
        "hash_tables_processed": False,
        "extraction_performed": False,
    }
