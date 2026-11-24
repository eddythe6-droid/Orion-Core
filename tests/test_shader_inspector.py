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
