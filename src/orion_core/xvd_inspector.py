"""Read-only metadata inspection for Xbox XVD/XVC containers.

This parser reads the public XVD header and bounded XVC manifest records only.
It never decrypts content, verifies signatures/hash trees, mounts volumes,
extracts files, or accesses protected payload data.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, BinaryIO

PAGE_SIZE = 0x1000
HEADER_SIZE = 0x3000
XVC_INFO_FIXED_SIZE = 0xDA8
XVC_REGION_HEADER_SIZE = 0x80
XVC_UPDATE_SEGMENT_SIZE = 0x0C
XVC_REGION_SPECIFIER_SIZE = 0x188
HASH_ENTRIES_PER_PAGE = PAGE_SIZE // 0x18

MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_REGION_COUNT = 4096
MAX_UPDATE_SEGMENTS = 250_000
MAX_REGION_SPECIFIERS = 4096
MAX_ENCRYPTION_KEYS = 0xC0

XVC_CONTENT_TYPES = {
    0x01: "title",
    0x06: "application",
    0x0F: "mte_application",
    0x10: "mte_title",
    0x18: "application_dlc",
    0x19: "title_dlc",
    0x1A: "universal_dlc",
}
CONTENT_TYPES = {
    0x00: "data", 0x01: "title", 0x02: "system_os", 0x03: "era_os",
    0x04: "scratch", 0x05: "reset_data", 0x06: "application",
    0x07: "host_os", 0x08: "x360_stfs", 0x09: "x360_fatx",
    0x0A: "x360_gdfx", 0x0B: "updater", 0x0C: "offline_updater",
    0x0D: "template", 0x0E: "mte_host", 0x0F: "mte_application",
    0x10: "mte_title", 0x11: "mte_era_os", 0x12: "era_tools",
    0x13: "system_tools", 0x14: "system_aux", 0x15: "acoustic_model",
    0x16: "system_codecs_volume", 0x17: "qaslt_package",
    0x18: "application_dlc", 0x19: "title_dlc", 0x1A: "universal_dlc",
    0x1B: "system_data_volume", 0x1C: "test_volume",
    0x1D: "hardware_test_volume", 0x1E: "kiosk_content",
    0x1F: "dev_package", 0x20: "host_profiler", 0x21: "roamable",
    0x22: "thin_provisioned", 0x23: "streaming_only_sra",
    0x24: "streaming_only_era", 0x25: "streaming_only_host",
    0x26: "quick_resume", 0x27: "host_data",
}
REGION_IDS = {
    0x40000001: "metadata_xvc",
    0x40000002: "metadata_filesystem",
    0x40000003: "unknown",
    0x40000004: "embedded_xvd",
    0x40000005: "header",
    0x40000006: "mutable_data",
}
REGION_FLAG_NAMES = {
    0x01: "resident",
    0x02: "initial_play",
    0x04: "preview",
    0x08: "filesystem_metadata",
    0x10: "present",
    0x20: "on_demand",
    0x40: "available",
}
VOLUME_FLAG_NAMES = {
    0x01: "read_only",
    0x02: "encryption_disabled",
    0x04: "data_integrity_disabled",
    0x08: "legacy_sector_size",
    0x10: "resiliency_enabled",
    0x20: "sra_read_only",
    0x40: "region_id_in_xts",
    0x80: "era_specific",
}


class XVDFormatError(ValueError):
    """Raised when an XVD/XVC header or bounded metadata table is malformed."""


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def _u64(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 8], "little")


def _guid(data: bytes, offset: int) -> str:
    raw = data[offset:offset + 16]
    return str(uuid.UUID(bytes_le=raw))


def _text_utf16(data: bytes) -> str:
    return data.decode("utf-16le", errors="replace").split("\x00", 1)[0].strip()


def _text_ascii(data: bytes) -> str:
    return data.decode("ascii", errors="replace").split("\x00", 1)[0].strip()


def _ceil_pages(size: int) -> int:
    return (size + PAGE_SIZE - 1) // PAGE_SIZE if size else 0


def _hash_tree_pages(hashed_pages: int, resilient: bool) -> int:
    """Reproduce the documented/publicly mapped XVD page-count calculation."""
    if hashed_pages <= 0:
        return 0
    pages = (hashed_pages + HASH_ENTRIES_PER_PAGE - 1) // HASH_ENTRIES_PER_PAGE
    if pages > 1:
        level = 1
        blocks = 2
        while blocks > 1 and level <= 3:
            denominator = HASH_ENTRIES_PER_PAGE ** (level + 1)
            blocks = (hashed_pages + denominator - 1) // denominator
            pages += blocks
            level += 1
    return pages * (2 if resilient else 1)


def _read_at(stream: BinaryIO, offset: int, length: int, file_size: int, label: str) -> bytes:
    if offset < 0 or length < 0 or offset > file_size or length > file_size - offset:
        raise XVDFormatError(f"{label} range is outside the file")
    stream.seek(offset)
    data = stream.read(length)
    if len(data) != length:
        raise XVDFormatError(f"{label} is truncated")
    return data


def _parse_xvc_manifest(
    stream: BinaryIO,
    file_size: int,
    manifest_offset: int,
    manifest_length: int,
) -> dict[str, Any]:
    if manifest_length < XVC_INFO_FIXED_SIZE:
        return {
            "parse_status": "manifest_too_small",
            "declared_length": manifest_length,
            "minimum_fixed_header_length": XVC_INFO_FIXED_SIZE,
        }
    if manifest_length > MAX_MANIFEST_BYTES:
        return {
            "parse_status": "manifest_over_safety_limit",
            "declared_length": manifest_length,
            "maximum_inspected_length": MAX_MANIFEST_BYTES,
        }
    fixed = _read_at(stream, manifest_offset, XVC_INFO_FIXED_SIZE, file_size, "XVC info header")
    version = _u32(fixed, 0xD10)
    region_count = _u32(fixed, 0xD14)
    key_count = _u16(fixed, 0xD1E)
    update_count = _u32(fixed, 0xD3C)
    specifier_count = _u32(fixed, 0xD50)

    if key_count > MAX_ENCRYPTION_KEYS:
        raise XVDFormatError("XVC key count exceeds the fixed key-ID table")
    if region_count > MAX_REGION_COUNT:
        raise XVDFormatError("XVC region count exceeds the safety limit")
    if update_count > MAX_UPDATE_SEGMENTS:
        raise XVDFormatError("XVC update-segment count exceeds the safety limit")
    if specifier_count > MAX_REGION_SPECIFIERS:
        raise XVDFormatError("XVC region-specifier count exceeds the safety limit")

    key_ids = []
    key_slots = []
    for index in range(key_count):
        key_offset = 0x10 + index * 16
        raw_key = fixed[key_offset:key_offset + 16]
        key_guid = _guid(fixed, key_offset) if any(raw_key) else None
        key_slots.append({
            "slot_index": index,
            "guid": key_guid,
            "populated": key_guid is not None,
        })
        if key_guid is not None:
            key_ids.append(key_guid)

    description = _text_utf16(fixed[0xC10:0xD10])
    content_id = _guid(fixed, 0)
    cursor = XVC_INFO_FIXED_SIZE
    regions: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    specifiers: list[dict[str, Any]] = []

    if version >= 1:
        required = region_count * XVC_REGION_HEADER_SIZE
        if required > manifest_length - cursor:
            raise XVDFormatError("XVC region-header table exceeds the declared manifest range")
        raw_regions = _read_at(stream, manifest_offset + cursor, required, file_size, "XVC region table")
        for index in range(region_count):
            base = index * XVC_REGION_HEADER_SIZE
            region_id = _u32(raw_regions, base)
            key_id = _u16(raw_regions, base + 4)
            flags = _u32(raw_regions, base + 8)
            first_segment = _u32(raw_regions, base + 0x0C)
            region_description = _text_utf16(raw_regions[base + 0x10:base + 0x50])
            region_offset = _u64(raw_regions, base + 0x50)
            region_length = _u64(raw_regions, base + 0x58)
            region_end_valid = (
                region_offset <= file_size and region_length <= file_size - region_offset
            )
            regions.append({
                "index": index,
                "region_id": region_id,
                "region_name": REGION_IDS.get(region_id, "unknown"),
                "key_id": key_id,
                "encrypted_by_key_reference": key_id != 0xFFFF,
                "key_guid": (
                    key_slots[key_id]["guid"]
                    if key_id != 0xFFFF and key_id < len(key_slots) else None
                ),
                "key_slot_reference_resolved": (
                    key_id == 0xFFFF or (
                        key_id < len(key_slots) and key_slots[key_id]["populated"]
                    )
                ),
                "flags": flags,
                "unknown_flag_bits": flags & ~sum(REGION_FLAG_NAMES.keys()),
                "padding_0x06": _u16(raw_regions, base + 0x06),
                "unknown_0x68": f"0x{_u64(raw_regions, base + 0x68):016X}",
                "unknown_0x70": f"0x{_u64(raw_regions, base + 0x70):016X}",
                "unknown_0x78": f"0x{_u64(raw_regions, base + 0x78):016X}",
                "flag_names": [name for bit, name in REGION_FLAG_NAMES.items() if flags & bit],
                "first_segment_index": first_segment,
                "first_segment_index_in_bounds": (
                    first_segment < update_count if update_count else None
                ),
                "description": region_description,
                "file_offset": region_offset,
                "length_bytes": region_length,
                "file_range_in_bounds": region_end_valid,
                "region_hash_or_id": f"0x{_u64(raw_regions, base + 0x60):016X}",
            })
        cursor += required

        required = update_count * XVC_UPDATE_SEGMENT_SIZE
        if required > manifest_length - cursor:
            raise XVDFormatError("XVC update-segment table exceeds the declared manifest range")
        raw_segments = _read_at(
            stream, manifest_offset + cursor, required, file_size, "XVC update-segment table"
        )
        for index in range(update_count):
            base = index * XVC_UPDATE_SEGMENT_SIZE
            segments.append({
                "index": index,
                "page_number": _u32(raw_segments, base),
                "hash_value": f"0x{_u64(raw_segments, base + 4):016X}",
            })
        cursor += required

    if version >= 2:
        required = specifier_count * XVC_REGION_SPECIFIER_SIZE
        if required > manifest_length - cursor:
            raise XVDFormatError("XVC region-specifier table exceeds the declared manifest range")
        raw_specifiers = _read_at(
            stream, manifest_offset + cursor, required, file_size, "XVC region-specifier table"
        )
        for index in range(specifier_count):
            base = index * XVC_REGION_SPECIFIER_SIZE
            specifiers.append({
                "index": index,
                "region_id": _u32(raw_specifiers, base),
                "key": _text_utf16(raw_specifiers[base + 8:base + 0x88]),
                "value": _text_utf16(raw_specifiers[base + 0x88:base + 0x188]),
            })
        cursor += required

    declared_region_ids = [item["region_id"] for item in regions]
    declared_region_id_set = set(declared_region_ids)
    duplicate_region_id_count = len(declared_region_ids) - len(declared_region_id_set)
    valid_ranges = sorted(
        (
            item["file_offset"],
            item["file_offset"] + item["length_bytes"],
            item["index"],
        )
        for item in regions
        if item["length_bytes"] > 0 and item["file_range_in_bounds"]
    )
    overlapping_region_count = 0
    furthest_region_end = -1
    for start, end, _index in valid_ranges:
        if start < furthest_region_end:
            overlapping_region_count += 1
        furthest_region_end = max(furthest_region_end, end)

    region_diagnostics = {
        "duplicate_region_id_count": duplicate_region_id_count,
        "unknown_region_id_count": sum(
            1 for region_id in declared_region_ids if region_id not in REGION_IDS
        ),
        "key_reference_out_of_range_count": sum(
            1 for item in regions
            if item["key_id"] != 0xFFFF and item["key_id"] >= key_count
        ),
        "key_reference_to_empty_slot_count": sum(
            1 for item in regions
            if item["key_id"] != 0xFFFF
            and item["key_id"] < len(key_slots)
            and not key_slots[item["key_id"]]["populated"]
        ),
        "first_segment_index_out_of_range_count": sum(
            1 for item in regions
            if update_count > 0 and item["first_segment_index"] >= update_count
        ),
        "region_file_range_out_of_bounds_count": sum(
            1 for item in regions if not item["file_range_in_bounds"]
        ),
        "regions_overlapping_another_region_count": overlapping_region_count,
        "specifier_without_matching_region_count": sum(
            1 for item in specifiers
            if item["region_id"] not in declared_region_id_set
        ),
        "initial_play_region_declared": (
            _u32(fixed, 0xD24) in declared_region_id_set
            if _u32(fixed, 0xD24) != 0 else None
        ),
        "preview_region_declared": (
            _u32(fixed, 0xD38) in declared_region_id_set
            if _u32(fixed, 0xD38) != 0 else None
        ),
        "interpretation": (
            "structural observations only; overlaps and unknown identifiers "
            "are not independently proven corruption"
        ),
    }

    return {
        "parse_status": "metadata_parsed",
        "version": version,
        "content_id": content_id,
        "description": description,
        "key_count_declared": key_count,
        "key_id_guids": key_ids,
        "key_slots": key_slots,
        "key_slots_populated": len(key_ids),
        "key_slots_empty": sum(1 for item in key_slots if not item["populated"]),
        "region_count": region_count if version >= 1 else 0,
        "regions": regions,
        "update_segment_count": update_count if version >= 1 else 0,
        "update_segments": segments,
        "region_specifier_count": specifier_count if version >= 2 else 0,
        "region_specifiers": specifiers,
        "region_diagnostics": region_diagnostics,
        "initial_play_region_id": _u32(fixed, 0xD24),
        "initial_play_offset": _u64(fixed, 0xD28),
        "preview_region_id": _u32(fixed, 0xD38),
        "preview_offset": _u64(fixed, 0xD40),
        "manifest_bytes_consumed": cursor,
        "manifest_bytes_declared": manifest_length,
        # Remaining bytes may be alignment padding or a newer/unknown table;
        # report them without interpreting them as malformed data.
        "manifest_bytes_uninterpreted": manifest_length - cursor,
        "payload_extracted": False,
        "cryptographic_checks_performed": False,
    }


def inspect_xvd_file(path: str | Path) -> dict[str, Any]:
    """Inspect one XVD/XVC header and, when applicable, its bounded XVC manifest."""
    target = Path(path)
    if not target.exists() or not target.is_file():
        raise XVDFormatError("path is not a regular file")
    if target.is_symlink():
        raise XVDFormatError("symbolic-link targets are not followed")
    file_size = target.stat().st_size
    if file_size < HEADER_SIZE:
        raise XVDFormatError("file is smaller than the fixed XVD header")
    with target.open("rb") as stream:
        header = _read_at(stream, 0, HEADER_SIZE, file_size, "XVD header")
        magic = header[0x200:0x208]
        if magic != b"msft-xvd":
            raise XVDFormatError("XVD header magic is not present at offset 0x200")

        volume_flags = _u32(header, 0x208)
        format_version = _u32(header, 0x20C)
        drive_size = _u64(header, 0x218)
        content_type = _u32(header, 0x284)
        embedded_length = _u32(header, 0x288)
        user_data_length = _u32(header, 0x28C)
        xvc_data_length = _u32(header, 0x290)
        dynamic_header_length = _u32(header, 0x294)
        block_size = _u32(header, 0x298)
        mutable_data_pages = header[0x470]
        is_xvc = content_type in XVC_CONTENT_TYPES
        integrity_disabled = bool(volume_flags & 0x04)
        resilient = bool(volume_flags & 0x10)

        embedded_pages = _ceil_pages(embedded_length)
        user_data_pages = _ceil_pages(user_data_length)
        xvc_info_pages = _ceil_pages(xvc_data_length)
        dynamic_header_pages = _ceil_pages(dynamic_header_length)
        drive_pages = _ceil_pages(drive_size)
        hashed_pages = drive_pages + user_data_pages + xvc_info_pages + dynamic_header_pages
        hash_pages = _hash_tree_pages(hashed_pages, resilient)
        mutable_data_length = mutable_data_pages * PAGE_SIZE
        mdu_offset = HEADER_SIZE + embedded_pages * PAGE_SIZE
        hash_tree_offset = mdu_offset + mutable_data_length
        user_data_offset = hash_tree_offset + (0 if integrity_disabled else hash_pages * PAGE_SIZE)
        xvc_info_offset = user_data_offset + user_data_pages * PAGE_SIZE

        extension_entries = []
        for index in range(4):
            offset = 0x29C + index * 0x18
            entry = {
                "code": _u32(header, offset),
                "length": _u32(header, offset + 4),
                "offset": _u64(header, offset + 8),
                "data_length": _u32(header, offset + 0x10),
            }
            if any(entry.values()):
                entry["data_range_in_bounds"] = (
                    entry["offset"] <= file_size
                    and entry["data_length"] <= file_size - entry["offset"]
                )
                extension_entries.append(entry)

        signature_area = header[:0x200]
        metadata: dict[str, Any] = {
            "valid_header": True,
            "container_format": "XVC" if is_xvc else "XVD",
            "magic": magic.decode("ascii"),
            "format_version": format_version,
            "volume_flags": volume_flags,
            "volume_flag_names": [
                name for bit, name in VOLUME_FLAG_NAMES.items() if volume_flags & bit
            ],
            "content_type": content_type,
            "content_type_name": CONTENT_TYPES.get(content_type, "unknown"),
            "xvc_content_type": is_xvc,
            "file_size_bytes": file_size,
            "drive_size_bytes": drive_size,
            "embedded_xvd_length": embedded_length,
            "user_data_length": user_data_length,
            "xvc_data_length": xvc_data_length,
            "dynamic_header_length": dynamic_header_length,
            "block_size": block_size,
            "sector_size_bytes": 512 if volume_flags & 0x08 else 4096,
            "encryption_status": (
                "disabled_in_header" if volume_flags & 0x02 else "encrypted_or_protected"
            ),
            "data_integrity_status": (
                "disabled_in_header" if integrity_disabled else "hash_tree_declared"
            ),
            "header_signature_area_nonzero": any(signature_area),
            "header_signature_cryptographically_verified": False,
            "top_hash_block_hash": header[0x240:0x260].hex(),
            "original_xvc_data_hash": header[0x260:0x280].hex(),
            "volume_id": _guid(header, 0x220),
            "user_id": _guid(header, 0x230),
            "sandbox_id": _text_ascii(header[0x38C:0x39C]),
            "product_id": _guid(header, 0x39C),
            "build_id": _guid(header, 0x3AC),
            "package_version_components": [
                _u16(header, 0x3BC + index * 2) for index in range(4)
            ],
            "required_system_version_components": [
                _u16(header, 0x494 + index * 2) for index in range(4)
            ],
            "embedded_xvd_build_id": _guid(header, 0x32C),
            "extension_entries": extension_entries,
            "layout": {
                "embedded_xvd_offset": HEADER_SIZE,
                "mutable_data_offset": mdu_offset,
                "hash_tree_offset": hash_tree_offset,
                "hash_tree_pages_calculated": hash_pages,
                "user_data_offset": user_data_offset,
                "xvc_info_offset": xvc_info_offset,
                "calculation_status": "metadata_layout_estimate",
            },
            "mutable_data_page_count": mutable_data_pages,
            "signature_verified": False,
            "hash_tree_verified": False,
            "payload_decrypted": False,
            "payload_extracted": False,
            "execution_performed": False,
            "compatibility_established": False,
        }

        if is_xvc:
            manifest_end_valid = (
                xvc_info_offset <= file_size
                and xvc_data_length <= file_size - xvc_info_offset
            )
            if not manifest_end_valid:
                metadata["xvc_manifest"] = {
                    "parse_status": "declared_manifest_range_out_of_file_bounds",
                    "offset": xvc_info_offset,
                    "declared_length": xvc_data_length,
                }
            elif xvc_data_length > MAX_MANIFEST_BYTES:
                metadata["xvc_manifest"] = {
                    "parse_status": "manifest_over_safety_limit",
                    "declared_length": xvc_data_length,
                    "maximum_inspected_length": MAX_MANIFEST_BYTES,
                }
            else:
                try:
                    metadata["xvc_manifest"] = _parse_xvc_manifest(
                        stream, file_size, xvc_info_offset, xvc_data_length
                    )
                except XVDFormatError as exc:
                    metadata["xvc_manifest"] = {
                        "parse_status": "malformed_or_truncated_manifest",
                        "error": str(exc),
                        "declared_length": xvc_data_length,
                        "cryptographic_checks_performed": False,
                    }
        else:
            metadata["xvc_manifest"] = None

    return metadata
