"""Bounded, read-only parser for core Portable Executable metadata."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

MAX_SECTIONS = 96
MAX_IMPORTS = 2048
MAX_NAME_BYTES = 260


class PEFormatError(ValueError):
    """The file is not a structurally valid PE within parser limits."""


def _read_at(stream, offset: int, size: int, file_size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > file_size:
        raise PEFormatError("header or table points outside the file")
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise PEFormatError("unexpected end of file")
    return data


def analyze_pe(path: str | Path) -> dict[str, Any]:
    """Extract PE machine, subsystem, sections and imported DLL names."""
    target = Path(path)
    try:
        file_size = target.stat().st_size
        with target.open("rb") as stream:
            if _read_at(stream, 0, 2, file_size) != b"MZ":
                raise PEFormatError("missing DOS MZ signature")
            pe_offset = struct.unpack("<I", _read_at(stream, 0x3C, 4, file_size))[0]
            if _read_at(stream, pe_offset, 4, file_size) != b"PE\0\0":
                raise PEFormatError("missing PE signature")
            coff = _read_at(stream, pe_offset + 4, 20, file_size)
            machine, section_count, timestamp, _, _, optional_size, characteristics = struct.unpack("<HHIIIHH", coff)
            if section_count > MAX_SECTIONS:
                raise PEFormatError(f"section count exceeds parser limit ({MAX_SECTIONS})")
            optional_offset = pe_offset + 24
            optional = _read_at(stream, optional_offset, optional_size, file_size)
            if len(optional) < 2:
                raise PEFormatError("optional header is truncated")
            magic = struct.unpack_from("<H", optional, 0)[0]
            if magic == 0x10B:
                kind, directory_offset, number_offset = "PE32", 96, 92
                image_base = struct.unpack_from("<I", optional, 28)[0] if len(optional) >= 32 else None
            elif magic == 0x20B:
                kind, directory_offset, number_offset = "PE32+", 112, 108
                image_base = struct.unpack_from("<Q", optional, 24)[0] if len(optional) >= 32 else None
            else:
                raise PEFormatError(f"unsupported optional-header magic 0x{magic:04x}")
            if len(optional) < directory_offset:
                raise PEFormatError("optional header is too short for data directories")
            entry_point = struct.unpack_from("<I", optional, 16)[0]
            subsystem = struct.unpack_from("<H", optional, 68)[0] if len(optional) >= 70 else None
            directory_count = struct.unpack_from("<I", optional, number_offset)[0] if len(optional) >= number_offset + 4 else 0
            import_rva = import_size = 0
            if directory_count > 1 and len(optional) >= directory_offset + 16:
                import_rva, import_size = struct.unpack_from("<II", optional, directory_offset + 8)

            section_offset = optional_offset + optional_size
            section_table = _read_at(stream, section_offset, section_count * 40, file_size)
            sections = []
            section_maps = []
            for index in range(section_count):
                raw = section_table[index * 40:(index + 1) * 40]
                name = raw[:8].split(b"\0", 1)[0].decode("ascii", errors="replace")
                virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", raw, 8)
                sections.append({
                    "name": name, "virtual_address": virtual_address,
                    "virtual_size": virtual_size, "raw_size": raw_size,
                    "raw_offset": raw_offset,
                })
                section_maps.append((virtual_address, max(virtual_size, raw_size), raw_offset, raw_size))

            def rva_to_offset(rva: int) -> int | None:
                for va, span, raw_offset, raw_size in section_maps:
                    if va <= rva < va + span:
                        delta = rva - va
                        return raw_offset + delta if delta < raw_size else None
                return None

            imports: list[str] = []
            if import_rva and import_size:
                import_offset = rva_to_offset(import_rva)
                if import_offset is not None:
                    max_descriptors = min(import_size // 20, MAX_IMPORTS)
                    for index in range(max_descriptors):
                        descriptor = _read_at(stream, import_offset + index * 20, 20, file_size)
                        original_thunk, _, _, name_rva, _ = struct.unpack("<IIIII", descriptor)
                        if not any(descriptor):
                            break
                        name_offset = rva_to_offset(name_rva)
                        if name_offset is None:
                            continue
                        name_bytes = bytearray()
                        for pos in range(MAX_NAME_BYTES):
                            byte = _read_at(stream, name_offset + pos, 1, file_size)
                            if byte == b"\0":
                                break
                            name_bytes.extend(byte)
                        if name_bytes:
                            imports.append(name_bytes.decode("ascii", errors="replace"))

    except OSError as exc:
        raise PEFormatError(f"cannot read PE file: {type(exc).__name__}: {exc}") from exc
    machine_names = {0x014C: "x86", 0x8664: "x86_64", 0x01C0: "ARM", 0x01C4: "ARMv7", 0xAA64: "ARM64"}
    subsystem_names = {1: "native", 2: "windows_gui", 3: "windows_console", 7: "posix_console", 9: "windows_ce_gui", 10: "efi_application"}
    return {
        "valid_pe_structure": True,
        "optional_header": kind,
        "machine": machine,
        "architecture": machine_names.get(machine, "unknown"),
        "image_base": image_base,
        "entry_point_rva": entry_point,
        "subsystem": subsystem,
        "subsystem_name": subsystem_names.get(subsystem, "unknown"),
        "characteristics": characteristics,
        "coff_timestamp": timestamp,
        "sections": sections,
        "imported_dlls": sorted(set(imports), key=str.casefold),
        "imports_truncated_or_unavailable": bool(import_rva and import_size and not imports),
        "parser_scope": "core_pe_headers_sections_and_imported_dll_names",
        "execution_performed": False,
    }
