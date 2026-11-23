"""Read-only parser for public Xbox 360 XEX2 wrapper metadata.

Does not decrypt, decompress, extract, patch, or execute the wrapped PE image.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

MAGIC = b"XEX2"
FIXED_HEADER_SIZE = 0x18
MAX_OPTIONAL_HEADERS = 4096

class XEXError(ValueError):
    """Malformed or unsupported XEX2 header."""


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def inspect_xex(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        with source.open("rb") as stream:
            data = stream.read()
    except OSError as exc:
        raise XEXError(f"cannot read XEX: {type(exc).__name__}: {exc}") from exc
    if len(data) < FIXED_HEADER_SIZE or data[:4] != MAGIC:
        raise XEXError("XEX2 signature or fixed header not found")
    module_flags = _u32(data, 4)
    pe_offset = _u32(data, 8)
    security_offset = _u32(data, 0x10)
    count = _u32(data, 0x14)
    if count > MAX_OPTIONAL_HEADERS:
        raise XEXError("optional header count exceeds safety limit")
    table_end = FIXED_HEADER_SIZE + count * 8
    if table_end > len(data):
        raise XEXError("optional header directory is truncated")
    if pe_offset > len(data) or security_offset > len(data):
        raise XEXError("header contains an out-of-file offset")
    optional: dict[str, int] = {}
    raw_headers = []
    for index in range(count):
        pos = FIXED_HEADER_SIZE + index * 8
        key, value = _u32(data, pos), _u32(data, pos + 4)
        raw_headers.append({"key": f"0x{key:08X}", "value": value})
        optional[f"0x{key:08X}"] = value

    def pointed_header(key: int, minimum: int) -> tuple[int, bytes] | None:
        value = optional.get(f"0x{key:08X}")
        if value is None:
            return None
        offset = value
        if offset > len(data) - 4:
            return None
        size = _u32(data, offset)
        if size < minimum or size > len(data) - offset:
            return None
        return offset, data[offset:offset + size]

    exec_info = None
    block = pointed_header(0x00040006, 0x18)
    if block:
        _, raw = block
        exec_info = {
            "media_id": _u32(raw, 0),
            "version_raw": _u32(raw, 4),
            "base_version_raw": _u32(raw, 8),
            "title_id": _u32(raw, 12),
            "platform": raw[16],
            "executable_type": raw[17],
            "disc_number": raw[18],
            "disc_count": raw[19],
            "savegame_id": _u32(raw, 20),
        }

    def inline(key: int) -> int | None:
        return optional.get(f"0x{key:08X}")

    return {
        "format": "XEX2",
        "module_flags": module_flags,
        "module_flag_bits": {
            "title_module": bool(module_flags & 1),
            "exports_to_title": bool(module_flags & 2),
            "system_debugger": bool(module_flags & 4),
            "dll_module": bool(module_flags & 8),
            "module_patch": bool(module_flags & 16),
            "user_mode": bool(module_flags & 128),
        },
        "pe_data_offset": pe_offset,
        "security_info_offset": security_offset,
        "optional_header_count": count,
        "optional_headers": raw_headers,
        "entry_point": inline(0x00010100),
        "image_base": inline(0x00010201),
        "original_base": inline(0x00010001),
        "execution_info": exec_info,
        "security_block_present": security_offset != 0,
        "security_block_parsed": False,
        "wrapped_pe_read": False,
        "decryption_performed": False,
        "decompression_performed": False,
        "extraction_performed": False,
        "metadata_only": True,
    }
