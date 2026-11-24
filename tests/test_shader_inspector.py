import struct

import pytest

from orion_core.shader_inspector import ShaderFormatError, inspect_shader_bytes


def _container(chunks):
    # DXBC header: signature, 16-byte hash placeholder, version, total size, count.
    header_size = 32 + len(chunks) * 4
    offsets = []
    payload = bytearray()
    for fourcc, body in chunks:
        offsets.append(header_size + len(payload))
        payload.extend(fourcc.encode("ascii"))
        payload.extend(struct.pack("<I", len(body)))
        payload.extend(body)
    total = header_size + len(payload)
    return (b"DXBC" + bytes(16) + struct.pack("<III", 1, total, len(chunks))
            + b"".join(struct.pack("<I", x) for x in offsets) + payload)


def test_inspect_dxbc_shader_model_chunk():
    # D3D pixel shader, shader model 5.0 token.
    token = (0 << 16) | (5 << 4) | 0
    report = inspect_shader_bytes(_container([("SHEX", struct.pack("<I", token) + b"\0" * 4)]))
    assert report["format"] == "dxbc_container"
    assert report["shader_programs"][0]["stage"] == "pixel"
    assert report["shader_programs"][0]["shader_model_major"] == 5
    assert report["checksum_verified"] is False


def test_inspect_dxil_program_header_without_claiming_validation():
    payload = struct.pack("<II4sIII", 0x10050, 6, b"DXIL", 0x106, 16, 4) + b"\0" * 8
    report = inspect_shader_bytes(_container([("DXIL", payload)]))
    program = report["dxil_programs"][0]
    assert program["header_assessment"] == "recognized_dxil_program_header"
    assert program["bitcode_range_within_chunk"] is True
    assert report["bytecode_validated"] is False


def test_rejects_bad_chunk_offset_and_non_dxbc_data():
    with pytest.raises(ShaderFormatError):
        inspect_shader_bytes(b"not shader")
    malformed = bytearray(_container([("SHEX", b"1234")]))
    struct.pack_into("<I", malformed, 32, 0xFFFFFFF0)
    with pytest.raises(ShaderFormatError):
        inspect_shader_bytes(bytes(malformed))

def test_inspects_spirv_header_without_parsing_instruction_stream():
    from orion_core.shader_inspector import inspect_spirv_bytes

    data = struct.pack("<5I", 0x07230203, 0x00010600, 7, 128, 0) + b"\x00\x00\x00\x00"
    report = inspect_spirv_bytes(data)
    assert report["format"] == "spirv"
    assert report["version"] == "1.6"
    assert report["id_bound"] == 128
    assert report["instruction_stream_parsed"] is False
    assert report["compatibility_established"] is False


def test_rejects_invalid_spirv_header_fields():
    from orion_core.shader_inspector import inspect_spirv_bytes

    with pytest.raises(ShaderFormatError, match="id bound"):
        inspect_spirv_bytes(struct.pack("<5I", 0x07230203, 0x00010000, 0, 0, 0))
    with pytest.raises(ShaderFormatError, match="schema"):
        inspect_spirv_bytes(struct.pack("<5I", 0x07230203, 0x00010000, 0, 1, 1))


def test_shader_file_detects_binary_magic_even_with_wrong_extension(tmp_path):
    from orion_core.shader_inspector import inspect_shader_file

    path = tmp_path / "shader.bin"
    path.write_bytes(struct.pack("<5I", 0x07230203, 0x00010000, 0, 10, 0))
    report = inspect_shader_file(path)
    assert report["format"] == "spirv"
    assert report["extension_format_match"] is True

def test_rejects_overlapping_dxbc_chunks():
    malformed = bytearray(_container([("SHEX", b"ABCD" + struct.pack("<I", 0)), ("SHDR", b"5678")]))
    first_offset = struct.unpack_from("<I", malformed, 32)[0]
    struct.pack_into("<I", malformed, 36, first_offset + 8)
    with pytest.raises(ShaderFormatError, match="overlapping"):
        inspect_shader_bytes(bytes(malformed))


def test_rejects_dxbc_container_with_duplicate_offsets():
    malformed = bytearray(_container([("SHEX", b"1234"), ("SHDR", b"5678")]))
    first_offset = struct.unpack_from("<I", malformed, 32)[0]
    struct.pack_into("<I", malformed, 36, first_offset)
    with pytest.raises(ShaderFormatError, match="duplicate"):
        inspect_shader_bytes(bytes(malformed))

def test_parses_common_rdef_resource_bindings():
    header = struct.pack("<7I", 0, 0, 1, 28, 0x50050, 0, 0)
    resource = struct.pack("<8I", 60, 2, 0, 4, 0, 3, 1, 0)
    payload = header + resource + b"albedoTexture\\x00"
    report = inspect_shader_bytes(_container([("RDEF", payload)]))
    reflection = report["chunks"][0]["resource_reflection"]
    assert reflection["assessment"] == "common_rdef_resource_table_parsed"
    assert reflection["resources"][0]["name"] == "albedoTexture"
    assert reflection["resources"][0]["input_type"] == "texture"
    assert reflection["resources"][0]["dimension"] == "texture2d"
    assert reflection["resources"][0]["bind_point"] == 3


def test_rdef_out_of_bounds_resource_table_is_reported_not_read():
    payload = struct.pack("<7I", 0, 0, 2, 28, 0, 0, 0)
    report = inspect_shader_bytes(_container([("RDEF", payload)]))
    reflection = report["chunks"][0]["resource_reflection"]
    assert reflection["assessment"] == "resource_binding_table_out_of_bounds"
    assert reflection["resources"] == []
