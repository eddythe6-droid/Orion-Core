"""Bounded, read-only parser for core Portable Executable metadata."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

MAX_SECTIONS = 96
MAX_IMPORTS = 2048
MAX_IMPORT_FUNCTIONS = 16384
MAX_FUNCTIONS_PER_DLL = 4096
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


def _read_c_string(stream, offset: int, file_size: int) -> str:
    data = bytearray()
    for pos in range(MAX_NAME_BYTES):
        byte = _read_at(stream, offset + pos, 1, file_size)
        if byte == b"\0":
            return data.decode("ascii", errors="replace")
        data.extend(byte)
    raise PEFormatError("import name is not null-terminated within parser limit")


def analyze_pe(path: str | Path) -> dict[str, Any]:
    """Extract PE headers, sections, imported DLLs and bounded import symbols."""
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
                kind, directory_offset, number_offset, thunk_size, ordinal_mask = "PE32", 96, 92, 4, 0x80000000
                image_base = struct.unpack_from("<I", optional, 28)[0] if len(optional) >= 32 else None
            elif magic == 0x20B:
                kind, directory_offset, number_offset, thunk_size, ordinal_mask = "PE32+", 112, 108, 8, 0x8000000000000000
                image_base = struct.unpack_from("<Q", optional, 24)[0] if len(optional) >= 32 else None
            else:
                raise PEFormatError(f"unsupported optional-header magic 0x{magic:04x}")
            if len(optional) < directory_offset:
                raise PEFormatError("optional header is too short for data directories")
            entry_point = struct.unpack_from("<I", optional, 16)[0]
            subsystem = struct.unpack_from("<H", optional, 68)[0] if len(optional) >= 70 else None
            directory_count = struct.unpack_from("<I", optional, number_offset)[0] if len(optional) >= number_offset + 4 else 0
            import_rva = import_size = delay_import_rva = delay_import_size = 0
            if directory_count > 1 and len(optional) >= directory_offset + 16:
                import_rva, import_size = struct.unpack_from("<II", optional, directory_offset + 8)
            if directory_count > 13 and len(optional) >= directory_offset + 14 * 8:
                delay_import_rva, delay_import_size = struct.unpack_from("<II", optional, directory_offset + 13 * 8)

            section_offset = optional_offset + optional_size
            section_table = _read_at(stream, section_offset, section_count * 40, file_size)
            sections, section_maps = [], []
            for index in range(section_count):
                raw = section_table[index * 40:(index + 1) * 40]
                name = raw[:8].split(b"\0", 1)[0].decode("ascii", errors="replace")
                virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", raw, 8)
                sections.append({"name": name, "virtual_address": virtual_address,
                    "virtual_size": virtual_size, "raw_size": raw_size, "raw_offset": raw_offset})
                section_maps.append((virtual_address, max(virtual_size, raw_size), raw_offset, raw_size))

            def rva_to_offset(rva: int) -> int | None:
                for va, span, raw_offset, raw_size in section_maps:
                    if va <= rva < va + span:
                        delta = rva - va
                        if delta >= raw_size or raw_offset + delta >= file_size:
                            return None
                        return raw_offset + delta
                return None

            imports: list[str] = []
            import_modules: list[dict[str, Any]] = []
            imported_functions: list[dict[str, Any]] = []
            delay_import_modules: list[dict[str, Any]] = []
            delay_imports_truncated = False
            imports_truncated = False
            if import_rva and import_size:
                import_offset = rva_to_offset(import_rva)
                if import_offset is not None:
                    max_descriptors = min(import_size // 20, MAX_IMPORTS)
                    for index in range(max_descriptors):
                        descriptor = _read_at(stream, import_offset + index * 20, 20, file_size)
                        original_thunk, _, _, name_rva, first_thunk = struct.unpack("<IIIII", descriptor)
                        if not any(descriptor):
                            break
                        name_offset = rva_to_offset(name_rva)
                        if name_offset is None:
                            imports_truncated = True
                            continue
                        dll_name = _read_c_string(stream, name_offset, file_size)
                        if not dll_name:
                            imports_truncated = True
                            continue
                        imports.append(dll_name)
                        thunk_rva = original_thunk or first_thunk
                        thunk_offset = rva_to_offset(thunk_rva) if thunk_rva else None
                        module_functions = []
                        if thunk_offset is None:
                            imports_truncated = True
                        else:
                            for thunk_index in range(MAX_FUNCTIONS_PER_DLL):
                                if len(imported_functions) >= MAX_IMPORT_FUNCTIONS:
                                    imports_truncated = True
                                    break
                                entry_offset = thunk_offset + thunk_index * thunk_size
                                if entry_offset + thunk_size > file_size:
                                    imports_truncated = True
                                    break
                                value = int.from_bytes(_read_at(stream, entry_offset, thunk_size, file_size), "little")
                                if value == 0:
                                    break
                                if value & ordinal_mask:
                                    symbol = {"kind": "ordinal", "ordinal": value & 0xFFFF}
                                else:
                                    hint_name_rva = value & (0x7FFFFFFF if thunk_size == 4 else 0x7FFFFFFFFFFFFFFF)
                                    hint_name_offset = rva_to_offset(hint_name_rva)
                                    if hint_name_offset is None:
                                        imports_truncated = True
                                        continue
                                    hint = struct.unpack("<H", _read_at(stream, hint_name_offset, 2, file_size))[0]
                                    symbol_name = _read_c_string(stream, hint_name_offset + 2, file_size)
                                    symbol = {"kind": "name", "name": symbol_name, "hint": hint}
                                item = {"dll": dll_name, **symbol}
                                imported_functions.append(item)
                                module_functions.append(symbol)
                            else:
                                imports_truncated = True
                        import_modules.append({"dll": dll_name, "functions": module_functions})
                    if max_descriptors == MAX_IMPORTS:
                        imports_truncated = True

            # IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT (13): 8-DWORD descriptors.
            if delay_import_rva and delay_import_size:
                delay_offset = rva_to_offset(delay_import_rva)
                if delay_offset is None:
                    delay_imports_truncated = True
                else:
                    max_delay_descriptors = min(delay_import_size // 32, MAX_IMPORTS)
                    terminated = False
                    for index in range(max_delay_descriptors):
                        descriptor_offset = delay_offset + index * 32
                        if descriptor_offset + 32 > file_size:
                            delay_imports_truncated = True
                            break
                        fields = struct.unpack("<IIIIIIII", _read_at(stream, descriptor_offset, 32, file_size))
                        if not any(fields):
                            terminated = True
                            break
                        attributes, name_value = fields[0], fields[1]
                        # grAttrs bit 0 means fields contain RVAs; otherwise VAs.
                        if attributes & 1:
                            name_rva = name_value
                        elif image_base is not None and name_value >= image_base:
                            name_rva = name_value - image_base
                        else:
                            delay_imports_truncated = True
                            continue
                        name_offset = rva_to_offset(name_rva)
                        if name_offset is None:
                            delay_imports_truncated = True
                            continue
                        try:
                            dll_name = _read_c_string(stream, name_offset, file_size)
                        except PEFormatError:
                            delay_imports_truncated = True
                            continue
                        if dll_name:
                            delay_import_modules.append({
                                "dll": dll_name,
                                "attributes": attributes,
                                "rva_based": bool(attributes & 1),
                            })
                        else:
                            delay_imports_truncated = True
                    if not terminated:
                        delay_imports_truncated = True

    except OSError as exc:
        raise PEFormatError(f"cannot read PE file: {type(exc).__name__}: {exc}") from exc
    machine_names = {0x014C: "x86", 0x8664: "x86_64", 0x01C0: "ARM", 0x01C4: "ARMv7", 0xAA64: "ARM64"}
    subsystem_names = {1: "native", 2: "windows_gui", 3: "windows_console", 7: "posix_console", 9: "windows_ce_gui", 10: "efi_application"}
    return {
        "valid_pe_structure": True, "optional_header": kind, "machine": machine,
        "architecture": machine_names.get(machine, "unknown"), "image_base": image_base,
        "entry_point_rva": entry_point, "subsystem": subsystem,
        "subsystem_name": subsystem_names.get(subsystem, "unknown"),
        "characteristics": characteristics, "coff_timestamp": timestamp,
        "sections": sections, "imported_dlls": sorted(set(imports), key=str.casefold),
        "import_modules": import_modules, "imported_functions": imported_functions,
        "delay_import_modules": delay_import_modules,
        "delay_imports_truncated_or_unavailable": delay_imports_truncated,
        "imports_truncated_or_unavailable": imports_truncated or bool(import_rva and import_size and not imports),
        "parser_scope": "core_pe_headers_sections_and_bounded_imported_symbols",
        "execution_performed": False,
    }
