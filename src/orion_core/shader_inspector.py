"""Bounded, read-only inspection of DXBC/DXIL shader container metadata."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

MAX_SHADER_BYTES = 16 * 1024 * 1024
MAX_CHUNKS = 4096
_STAGE_NAMES = {
    0: "pixel", 1: "vertex", 2: "geometry", 3: "hull",
    4: "domain", 5: "compute", 6: "reserved_6", 7: "reserved_7",
    8: "reserved_8", 9: "reserved_9", 10: "reserved_10",
}


class ShaderFormatError(ValueError):
    """Raised when a shader container is malformed or exceeds parser bounds."""


_RDEF_INPUT_TYPES = {
    0: "constant_buffer", 1: "texture_buffer", 2: "texture", 3: "sampler",
    4: "typed_uav", 5: "structured", 6: "rw_structured", 7: "byte_address",
    8: "rw_byte_address", 9: "append_structured", 10: "consume_structured",
    11: "counter",
}
_RDEF_DIMENSIONS = {
    0: "unknown", 1: "buffer", 2: "texture1d", 3: "texture1d_array",
    4: "texture2d", 5: "texture2d_array", 6: "texture2d_ms",
    7: "texture2d_ms_array", 8: "texture3d", 9: "texture_cube",
    10: "texture_cube_array", 11: "buffer_ex",
}


def _read_rdef_string(payload: bytes, offset: int) -> str | None:
    if offset < 0 or offset >= len(payload):
        return None
    end = payload.find(b"\x00", offset, min(len(payload), offset + 4096))
    if end < 0:
        return None
    return payload[offset:end].decode("utf-8", errors="replace")


def _inspect_rdef(payload: bytes) -> dict[str, Any]:
    """Parse the common 28-byte RDEF header and 32-byte resource bindings only."""
    if len(payload) < 28:
        return {"assessment": "truncated_rdef_header", "resources": []}
    cb_count, cb_offset, resource_count, resource_offset, target, flags, creator_offset = struct.unpack_from(
        "<7I", payload, 0
    )
    if resource_count > 16384:
        return {"assessment": "resource_count_exceeds_parser_limit", "resources": []}
    table_end = resource_offset + resource_count * 32
    if (resource_count and resource_offset < 28) or table_end > len(payload):
        return {"assessment": "resource_binding_table_out_of_bounds", "resources": []}
    resources = []
    for index in range(resource_count):
        pos = resource_offset + index * 32
        name_offset, input_type, return_type, dimension, sample_count, bind_point, bind_count, bind_flags = struct.unpack_from(
            "<8I", payload, pos
        )
        name = _read_rdef_string(payload, name_offset)
        resources.append({
            "name": name,
            "name_offset": name_offset,
            "input_type_id": input_type,
            "input_type": _RDEF_INPUT_TYPES.get(input_type, "unknown"),
            "return_type_id": return_type,
            "dimension_id": dimension,
            "dimension": _RDEF_DIMENSIONS.get(dimension, "unknown"),
            "sample_count": sample_count,
            "bind_point": bind_point,
            "bind_count": bind_count,
            "bind_flags": bind_flags,
        })
    creator = _read_rdef_string(payload, creator_offset) if creator_offset else None
    return {
        "assessment": "common_rdef_resource_table_parsed",
        "constant_buffer_count": cb_count,
        "constant_buffer_table_offset": cb_offset,
        "resource_count": resource_count,
        "resource_table_offset": resource_offset,
        "target_word": target,
        "flags": flags,
        "creator": creator,
        "resources": resources,
        "constant_buffer_records_parsed": False,
        "limitations": [
            "Only the common RDEF header and 32-byte resource-binding records are parsed.",
            "Constant-buffer records, variable layouts, signatures, and target-specific RDEF variants are not decoded.",
        ],
    }


def inspect_shader_bytes(data: bytes) -> dict[str, Any]:
    """Read container/chunk metadata; never validates signatures or executes bytecode."""
    if len(data) < 4 or data[:4] != b"DXBC":
        raise ShaderFormatError("missing DXBC container signature")
    if len(data) < 32:
        raise ShaderFormatError("DXBC header is truncated")
    if len(data) > MAX_SHADER_BYTES:
        raise ShaderFormatError(f"shader exceeds parser limit ({MAX_SHADER_BYTES} bytes)")
    version, declared_size, chunk_count = struct.unpack_from("<III", data, 20)
    if declared_size < 32 or declared_size > len(data):
        raise ShaderFormatError("declared DXBC container size is outside the file")
    if chunk_count > MAX_CHUNKS:
        raise ShaderFormatError(f"chunk count exceeds parser limit ({MAX_CHUNKS})")
    table_end = 32 + chunk_count * 4
    if table_end > declared_size:
        raise ShaderFormatError("DXBC chunk-offset table is truncated")

    chunks = []
    stages = []
    dxil_programs = []
    seen_offsets = set()
    chunk_ranges: list[tuple[int, int]] = []
    for index in range(chunk_count):
        offset = struct.unpack_from("<I", data, 32 + index * 4)[0]
        if offset in seen_offsets:
            raise ShaderFormatError("duplicate DXBC chunk offset")
        seen_offsets.add(offset)
        if offset < table_end or offset + 8 > declared_size:
            raise ShaderFormatError("DXBC chunk header points outside container")
        fourcc_bytes = data[offset:offset + 4]
        try:
            fourcc = fourcc_bytes.decode("ascii")
        except UnicodeDecodeError:
            fourcc = fourcc_bytes.decode("ascii", errors="replace")
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        if payload_end > declared_size:
            raise ShaderFormatError("DXBC chunk payload points outside container")
        if any(offset < end and start < payload_end for start, end in chunk_ranges):
            raise ShaderFormatError("overlapping DXBC chunk ranges")
        chunk_ranges.append((offset, payload_end))
        payload = data[payload_start:payload_end]
        chunk_info: dict[str, Any] = {"fourcc": fourcc, "size_bytes": chunk_size}
        if fourcc in ("SHDR", "SHEX"):
            if len(payload) >= 4:
                token = struct.unpack_from("<I", payload, 0)[0]
                stage_id = (token >> 16) & 0xFFFF
                stage = _STAGE_NAMES.get(stage_id, "unknown")
                stage_info = {
                    "stage": stage,
                    "stage_id": stage_id,
                    "shader_model_major": (token >> 4) & 0xF,
                    "shader_model_minor": token & 0xF,
                    "source_chunk": fourcc,
                }
                chunk_info["shader_program"] = stage_info
                stages.append(stage_info)
            else:
                chunk_info["shader_program"] = {"assessment": "truncated_program_header"}
        elif fourcc == "RDEF":
            chunk_info["resource_reflection"] = _inspect_rdef(payload)
        elif fourcc == "DXIL":
            program: dict[str, Any] = {"container_chunk": "DXIL"}
            if len(payload) >= 24 and payload[8:12] == b"DXIL":
                program.update({
                    "program_version_token": struct.unpack_from("<I", payload, 0)[0],
                    "program_size_dwords": struct.unpack_from("<I", payload, 4)[0],
                    "dxil_version": struct.unpack_from("<I", payload, 12)[0],
                    "bitcode_offset": struct.unpack_from("<I", payload, 16)[0],
                    "bitcode_size": struct.unpack_from("<I", payload, 20)[0],
                    "header_assessment": "recognized_dxil_program_header",
                })
                bitcode_start = 8 + program["bitcode_offset"]
                bitcode_end = bitcode_start + program["bitcode_size"]
                program["bitcode_range_within_chunk"] = (
                    bitcode_start >= 0 and bitcode_end >= bitcode_start and bitcode_end <= len(payload)
                )
            else:
                program["header_assessment"] = "dxil_chunk_without_recognized_program_header"
            chunk_info["dxil_program"] = program
            dxil_programs.append(program)
        chunks.append(chunk_info)

    return {
        "format": "dxbc_container",
        "container_version": version,
        "declared_size_bytes": declared_size,
        "trailing_bytes": len(data) - declared_size,
        "chunk_count": chunk_count,
        "chunks": chunks,
        "shader_programs": stages,
        "dxil_programs": dxil_programs,
        "metadata_scope": "container_chunk_and_shader_model_headers_only",
        "checksum_verified": False,
        "bytecode_validated": False,
        "execution_performed": False,
        "compatibility_established": False,
        "limitations": [
            "The DXBC hash/checksum is not verified.",
            "Shader instructions, signatures, root signatures, and pipeline state are not decoded; only common RDEF resource-binding records are inventoried.",
            "DXIL bitcode is not parsed or validated.",
            "A structurally recognized container does not prove driver or Xbox/Windows compatibility.",
        ],
    }


def inspect_spirv_bytes(data: bytes) -> dict[str, Any]:
    """Recognize and validate only the fixed SPIR-V module header."""
    if len(data) < 4 or data[:4] not in (b"\x03\x02#\x07", b"\x07#\x02\x03"):
        raise ShaderFormatError("missing SPIR-V magic")
    if len(data) < 20:
        raise ShaderFormatError("SPIR-V module header is truncated")
    endian = "<" if data[:4] == b"\x03\x02#\x07" else ">"
    magic, version, generator, bound, schema = struct.unpack_from(endian + "5I", data, 0)
    major = (version >> 16) & 0xFF
    minor = (version >> 8) & 0xFF
    version_assessment = "recognized_version" if major == 1 and minor <= 6 else "unknown_or_future_version"
    if bound == 0:
        raise ShaderFormatError("SPIR-V id bound must be non-zero")
    if schema != 0:
        raise ShaderFormatError("SPIR-V reserved schema word must be zero")
    return {
        "format": "spirv", "magic": f"0x{magic:08x}",
        "endianness": "little" if endian == "<" else "big",
        "version_word": f"0x{version:08x}", "version": f"{major}.{minor}",
        "version_assessment": version_assessment, "generator_word": generator,
        "id_bound": bound, "schema": schema, "module_bytes": len(data),
        "instruction_stream_parsed": False, "bytecode_validated": False,
        "execution_performed": False, "compatibility_established": False,
        "limitations": [
            "Only the fixed five-word SPIR-V header is inspected.",
            "Instruction stream, capabilities, extensions, entry points, descriptors, and execution modes are not decoded.",
        ],
    }


def inspect_shader_file(path: str | Path) -> dict[str, Any]:
    """Inspect a bounded DXBC or SPIR-V file; no archive extraction is performed."""
    target = Path(path)
    size = target.stat().st_size
    if size > MAX_SHADER_BYTES:
        return {
            "assessment": "size_limit_exceeded", "size_bytes": size,
            "parser_limit_bytes": MAX_SHADER_BYTES, "bytecode_validated": False,
            "execution_performed": False,
        }
    with target.open("rb") as stream:
        data = stream.read(MAX_SHADER_BYTES + 1)
    if data.startswith(b"DXBC"):
        report = inspect_shader_bytes(data)
    elif data.startswith((b"\x03\x02#\x07", b"\x07#\x02\x03")):
        report = inspect_spirv_bytes(data)
    else:
        raise ShaderFormatError("unrecognized shader binary signature")
    suffix = target.suffix.lower()
    expected = {".cso": {"dxbc", "spirv"}, ".dxbc": {"dxbc"}, ".dxil": {"dxbc"}, ".spv": {"spirv"}}
    actual = "spirv" if report["format"] == "spirv" else "dxbc"
    report["file_extension"] = suffix
    report["extension_format_match"] = suffix not in expected or actual in expected[suffix]
    if not report["extension_format_match"]:
        report["extension_assessment"] = "extension_does_not_match_detected_binary_format"
    return report
