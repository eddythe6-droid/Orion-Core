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
MAX_EXPORTS = 10000
MAX_CERTIFICATES = 64
MAX_CERTIFICATE_TABLE_BYTES = 64 * 1024 * 1024


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
        parser_warnings: list[str] = []
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
            linker_version = f"{optional[2]}.{optional[3]}" if len(optional) >= 4 else None
            section_alignment = struct.unpack_from("<I", optional, 32)[0] if len(optional) >= 36 else None
            file_alignment = struct.unpack_from("<I", optional, 36)[0] if len(optional) >= 40 else None
            size_of_image = struct.unpack_from("<I", optional, 56)[0] if len(optional) >= 60 else None
            size_of_headers = struct.unpack_from("<I", optional, 60)[0] if len(optional) >= 64 else None
            checksum = struct.unpack_from("<I", optional, 64)[0] if len(optional) >= 68 else None
            dll_characteristics = struct.unpack_from("<H", optional, 70)[0] if len(optional) >= 72 else 0
            dll_characteristic_flags = {
                "high_entropy_va": bool(dll_characteristics & 0x0020),
                "dynamic_base": bool(dll_characteristics & 0x0040),
                "force_integrity": bool(dll_characteristics & 0x0080),
                "nx_compatible": bool(dll_characteristics & 0x0100),
                "no_isolation": bool(dll_characteristics & 0x0200),
                "no_seh": bool(dll_characteristics & 0x0400),
                "appcontainer": bool(dll_characteristics & 0x1000),
                "guard_cf": bool(dll_characteristics & 0x4000),
                "terminal_server_aware": bool(dll_characteristics & 0x8000),
            }
            directory_names = (
                "export", "import", "resource", "exception", "security",
                "base_relocation", "debug", "architecture", "global_ptr",
                "tls", "load_config", "bound_import", "iat", "delay_import",
                "clr", "reserved",
            )
            available_directories = max(0, (len(optional) - directory_offset) // 8)
            if directory_count > available_directories:
                parser_warnings.append(
                    f"Optional header declares {directory_count} data directories, "
                    f"but only {available_directories} fit in the optional header."
                )
            data_directories: list[dict[str, Any]] = []
            for directory_index in range(min(directory_count, available_directories, len(directory_names))):
                value, size = struct.unpack_from("<II", optional, directory_offset + directory_index * 8)
                data_directories.append({
                    "index": directory_index,
                    "name": directory_names[directory_index],
                    "address_kind": "file_offset" if directory_index == 4 else "rva",
                    "address": value,
                    "size": size,
                })
            directory_by_name = {item["name"]: item for item in data_directories}
            security_directory = directory_by_name.get("security", {"address": 0, "size": 0})
            export_rva = export_size = import_rva = import_size = delay_import_rva = delay_import_size = 0
            if directory_count > 0 and len(optional) >= directory_offset + 8:
                export_rva, export_size = struct.unpack_from("<II", optional, directory_offset)
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
                section_characteristics = struct.unpack_from("<I", raw, 36)[0]
                raw_range_valid = raw_offset + raw_size <= file_size if raw_size else True
                if not raw_range_valid:
                    parser_warnings.append(f"Section {name!r} raw range extends beyond end of file.")
                section_flags = {
                    "contains_code": bool(section_characteristics & 0x00000020),
                    "contains_initialized_data": bool(section_characteristics & 0x00000040),
                    "contains_uninitialized_data": bool(section_characteristics & 0x00000080),
                    "memory_discardable": bool(section_characteristics & 0x02000000),
                    "memory_not_cached": bool(section_characteristics & 0x04000000),
                    "memory_not_paged": bool(section_characteristics & 0x08000000),
                    "memory_shared": bool(section_characteristics & 0x10000000),
                    "memory_execute": bool(section_characteristics & 0x20000000),
                    "memory_read": bool(section_characteristics & 0x40000000),
                    "memory_write": bool(section_characteristics & 0x80000000),
                }
                sections.append({
                    "name": name,
                    "virtual_address": virtual_address,
                    "virtual_size": virtual_size,
                    "raw_size": raw_size,
                    "raw_offset": raw_offset,
                    "raw_range_valid": raw_range_valid,
                    "characteristics": section_characteristics,
                    "flags": section_flags,
                })
                section_maps.append((virtual_address, max(virtual_size, raw_size), raw_offset, raw_size))

            raw_ranges = sorted(
                (item["raw_offset"], item["raw_offset"] + item["raw_size"], item["name"])
                for item in sections if item["raw_size"] and item["raw_range_valid"]
            )
            for previous, current in zip(raw_ranges, raw_ranges[1:]):
                if current[0] < previous[1]:
                    parser_warnings.append(
                        f"Raw section ranges overlap: {previous[2]!r} and {current[2]!r}."
                    )

            def rva_to_offset(rva: int) -> int | None:
                if rva < 0:
                    return None
                if size_of_headers and rva < size_of_headers and rva < file_size:
                    return rva
                for va, span, raw_offset, raw_size in section_maps:
                    if va <= rva < va + span:
                        delta = rva - va
                        if delta >= raw_size or raw_offset + delta >= file_size:
                            return None
                        return raw_offset + delta
                return None

            certificate_records: list[dict[str, Any]] = []
            certificate_offset = int(security_directory.get("address", 0))
            certificate_size = int(security_directory.get("size", 0))
            certificate_table_status = "absent"
            if certificate_offset or certificate_size:
                if not certificate_offset or not certificate_size:
                    certificate_table_status = "invalid_directory_entry"
                    parser_warnings.append("Security directory has only one of file offset and size set.")
                elif certificate_offset + certificate_size > file_size:
                    certificate_table_status = "out_of_file_range"
                    parser_warnings.append("Certificate table points beyond end of file.")
                elif certificate_size > MAX_CERTIFICATE_TABLE_BYTES:
                    certificate_table_status = "over_parser_limit"
                    parser_warnings.append("Certificate table exceeds bounded metadata parser limit.")
                else:
                    certificate_table_status = "present_unparsed"
                    cursor = certificate_offset
                    table_end = certificate_offset + certificate_size
                    while cursor + 8 <= table_end and len(certificate_records) < MAX_CERTIFICATES:
                        header = _read_at(stream, cursor, 8, file_size)
                        record_length, revision, certificate_type = struct.unpack("<IHH", header)
                        if record_length < 8 or cursor + record_length > table_end:
                            certificate_table_status = "malformed_record"
                            parser_warnings.append("Malformed WIN_CERTIFICATE record length.")
                            break
                        type_names = {
                            0x0001: "X509",
                            0x0002: "PKCS_SIGNED_DATA",
                            0x0003: "RESERVED",
                            0x0004: "TS_STACK_SIGNED",
                            0x0006: "EFI_PKCS115",
                            0x0007: "EFI_GUID",
                        }
                        certificate_records.append({
                            "file_offset": cursor,
                            "length": record_length,
                            "revision": revision,
                            "revision_name": {
                                0x0100: "WIN_CERT_REVISION_1_0",
                                0x0200: "WIN_CERT_REVISION_2_0",
                            }.get(revision, "unknown"),
                            "certificate_type": certificate_type,
                            "certificate_type_name": type_names.get(certificate_type, "unknown"),
                        })
                        aligned_length = (record_length + 7) & ~7
                        if cursor + aligned_length > table_end:
                            if cursor + record_length == table_end:
                                cursor = table_end
                            else:
                                certificate_table_status = "misaligned_record"
                                parser_warnings.append("WIN_CERTIFICATE record alignment exceeds certificate table.")
                                break
                        else:
                            cursor += aligned_length
                    if len(certificate_records) >= MAX_CERTIFICATES and cursor < table_end:
                        certificate_table_status = "record_limit_reached"
                        parser_warnings.append("Certificate record count exceeds parser limit.")
                    elif cursor == table_end and certificate_table_status == "present_unparsed":
                        certificate_table_status = "records_parsed"
                    elif cursor < table_end and certificate_table_status == "present_unparsed":
                        certificate_table_status = "trailing_bytes"
                        parser_warnings.append("Certificate table contains trailing bytes shorter than a record header.")
            authenticode_metadata = {
                "table_present": bool(certificate_offset and certificate_size),
                "table_file_offset": certificate_offset,
                "table_size": certificate_size,
                "parse_status": certificate_table_status,
                "records": certificate_records,
                "cryptographic_signature_verified": False,
                "authenticode_digest_verified": False,
                "publisher_identity_verified": False,
                "interpretation": "Certificate-table presence and record framing only; no cryptographic or trust-chain verification was performed.",
            }

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
 
            # IMAGE_DIRECTORY_ENTRY_EXPORT (0): bounded export directory inventory.
            exported_functions: list[dict[str, Any]] = []
            exports_truncated = False
            export_directory_valid = False
            if export_rva and export_size:
                export_offset = rva_to_offset(export_rva)
                if export_offset is None or export_size < 40:
                    exports_truncated = True
                else:
                    directory = _read_at(stream, export_offset, 40, file_size)
                    (_, _, _, _, _, ordinal_base, function_count, name_count,
                     functions_rva, names_rva, ordinals_rva) = struct.unpack("<IIHHIIIIIII", directory)
                    export_directory_valid = True
                    if function_count > MAX_EXPORTS or name_count > MAX_EXPORTS:
                        exports_truncated = True
                    bounded_functions = min(function_count, MAX_EXPORTS)
                    bounded_names = min(name_count, MAX_EXPORTS)
                    functions_offset = rva_to_offset(functions_rva) if functions_rva else None
                    names_offset = rva_to_offset(names_rva) if names_rva else None
                    ordinals_offset = rva_to_offset(ordinals_rva) if ordinals_rva else None
                    if bounded_functions and functions_offset is None:
                        exports_truncated = True
                    named_exports: dict[int, list[str]] = {}
                    if bounded_names and (names_offset is None or ordinals_offset is None):
                        exports_truncated = True
                    elif names_offset is not None and ordinals_offset is not None:
                        for index in range(bounded_names):
                            name_ptr = int.from_bytes(_read_at(stream, names_offset + index * 4, 4, file_size), "little")
                            ordinal_index = int.from_bytes(_read_at(stream, ordinals_offset + index * 2, 2, file_size), "little")
                            if ordinal_index >= function_count:
                                exports_truncated = True
                                continue
                            name_ptr_offset = rva_to_offset(name_ptr)
                            if name_ptr_offset is None:
                                exports_truncated = True
                                continue
                            try:
                                export_name = _read_c_string(stream, name_ptr_offset, file_size)
                            except PEFormatError:
                                exports_truncated = True
                                continue
                            named_exports.setdefault(ordinal_index, []).append(export_name)
                    if functions_offset is not None:
                        for index in range(bounded_functions):
                            function_rva = int.from_bytes(_read_at(stream, functions_offset + index * 4, 4, file_size), "little")
                            if function_rva == 0:
                                continue
                            forwarder = None
                            if export_rva <= function_rva < export_rva + export_size:
                                forwarder_offset = rva_to_offset(function_rva)
                                if forwarder_offset is not None:
                                    try:
                                        forwarder = _read_c_string(stream, forwarder_offset, file_size)
                                    except PEFormatError:
                                        exports_truncated = True
                            exported_functions.append({
                                "ordinal": ordinal_base + index,
                                "rva": function_rva,
                                "names": named_exports.get(index, []),
                                "forwarder": forwarder,
                                "is_forwarder": forwarder is not None,
                            })

    except OSError as exc:
        raise PEFormatError(f"cannot read PE file: {type(exc).__name__}: {exc}") from exc
    machine_names = {0x014C: "x86", 0x8664: "x86_64", 0x01C0: "ARM", 0x01C4: "ARMv7", 0xAA64: "ARM64"}
    subsystem_names = {1: "native", 2: "windows_gui", 3: "windows_console", 7: "posix_console", 9: "windows_ce_gui", 10: "efi_application"}
    max_raw_end = max(
        (item["raw_offset"] + item["raw_size"] for item in sections
         if item["raw_size"] and item["raw_range_valid"]),
        default=0,
    )
    section_table_end = section_offset + section_count * 40
    mapped_file_end = max(max_raw_end, size_of_headers or section_table_end)
    trailing_data = {
        "start_offset": mapped_file_end,
        "size_bytes": max(0, file_size - mapped_file_end),
        "may_include_certificate_table_or_non_section_data": True,
    }
    return {
        "valid_pe_structure": True,
        "file_size_bytes": file_size,
        "pe_header_file_offset": pe_offset,
        "coff_header_file_offset": pe_offset + 4,
        "optional_header_file_offset": optional_offset,
        "section_table_file_offset": section_offset,
        "optional_header": kind,
        "machine": machine,
        "architecture": machine_names.get(machine, "unknown"),
        "image_base": image_base,
        "entry_point_rva": entry_point,
        "entry_point_file_offset": rva_to_offset(entry_point) if entry_point else None,
        "subsystem": subsystem,
        "subsystem_name": subsystem_names.get(subsystem, "unknown"),
        "linker_version": linker_version,
        "section_alignment": section_alignment,
        "file_alignment": file_alignment,
        "size_of_image": size_of_image,
        "size_of_headers": size_of_headers,
        "checksum_field": checksum,
        "dll_characteristics": dll_characteristics,
        "dll_characteristic_flags": dll_characteristic_flags,
        "data_directory_count_declared": directory_count,
        "data_directories": data_directories,
        "authenticode_metadata": authenticode_metadata,
        "trailing_data": trailing_data,
        "parser_warnings": parser_warnings,
        "characteristics": characteristics,
        "coff_timestamp": timestamp,
        "sections": sections, "exported_functions": exported_functions,
        "export_directory_valid": export_directory_valid,
        "exports_truncated_or_unavailable": exports_truncated,
        "imported_dlls": sorted(set(imports), key=str.casefold),
        "import_modules": import_modules, "imported_functions": imported_functions,
        "delay_import_modules": delay_import_modules,
        "delay_imports_truncated_or_unavailable": delay_imports_truncated,
        "imports_truncated_or_unavailable": imports_truncated or bool(import_rva and import_size and not imports),
        "parser_scope": "bounded_pe_headers_sections_data_directories_authenticode_table_imports_and_exports",
        "execution_performed": False,
    }
