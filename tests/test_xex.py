import struct

import pytest

from orion_core.xex import XEXError, inspect_xex


def make_xex(path):
    data = bytearray(0x100)
    data[:4] = b"XEX2"
    struct.pack_into(">I", data, 4, 0x81)
    struct.pack_into(">I", data, 8, 0xF0)
    struct.pack_into(">I", data, 0x10, 0x80)
    struct.pack_into(">I", data, 0x14, 4)
    headers = [
        (0x00010100, 0x12345678),
        (0x00010201, 0x82000000),
        (0x00040006, 0x40),
        (0x000183FF, 0x70),
    ]
    for i, (key, value) in enumerate(headers):
        struct.pack_into(">II", data, 0x18 + i * 8, key, value)
    struct.pack_into(">I", data, 0x40, 0x18)
    struct.pack_into(">IIII", data, 0x44, 0xAABBCCDD, 1, 2, 0x4D530001)
    data[0x54:0x58] = bytes((2, 0, 1, 2))
    struct.pack_into(">I", data, 0x58, 99)
    struct.pack_into(">I", data, 0x70, 8)
    path.write_bytes(data)


def test_reads_xex2_public_wrapper_metadata(tmp_path):
    path = tmp_path / "default.xex"
    make_xex(path)
    report = inspect_xex(path)
    assert report["entry_point"] == 0x12345678
    assert report["image_base"] == 0x82000000
    assert report["execution_info"]["title_id"] == 0x4D530001
    assert report["execution_info"]["disc_count"] == 2
    assert report["decryption_performed"] is False


def test_rejects_bad_magic_and_truncated_optional_directory(tmp_path):
    path = tmp_path / "bad.xex"
    path.write_bytes(b"NOPE" + bytes(40))
    with pytest.raises(XEXError, match="signature"):
        inspect_xex(path)
    data = bytearray(0x18)
    data[:4] = b"XEX2"
    struct.pack_into(">I", data, 0x14, 3)
    path.write_bytes(data)
    with pytest.raises(XEXError, match="truncated"):
        inspect_xex(path)


def test_rejects_unreasonable_optional_header_count(tmp_path):
    path = tmp_path / "bad.xex"
    data = bytearray(0x18)
    data[:4] = b"XEX2"
    struct.pack_into(">I", data, 0x14, 5000)
    path.write_bytes(data)
    with pytest.raises(XEXError, match="safety limit"):
        inspect_xex(path)
