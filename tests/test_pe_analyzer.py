import struct

import pytest

from orion_core.pe_analyzer import PEFormatError, analyze_pe


def make_minimal_pe(path, *, machine=0x8664, magic=0x20B):
    data = bytearray(0x400)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, machine, 1, 123456, 0, 0, 0xF0, 0x22)
    opt = 0x98
    struct.pack_into("<H", data, opt, magic)
    struct.pack_into("<I", data, opt + 16, 0x1000)
    if magic == 0x20B:
        struct.pack_into("<Q", data, opt + 24, 0x140000000)
        struct.pack_into("<I", data, opt + 108, 16)
    else:
        struct.pack_into("<I", data, opt + 28, 0x400000)
        struct.pack_into("<I", data, opt + 92, 16)
    struct.pack_into("<H", data, opt + 68, 3)
    sec = opt + 0xF0
    data[sec:sec + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, sec + 8, 0x100, 0x1000, 0x200, 0x200)
    path.write_bytes(data)


def test_analyzes_pe64_architecture_and_sections(tmp_path):
    path = tmp_path / "sample.exe"
    make_minimal_pe(path)
    report = analyze_pe(path)
    assert report["valid_pe_structure"] is True
    assert report["optional_header"] == "PE32+"
    assert report["architecture"] == "x86_64"
    assert report["subsystem_name"] == "windows_console"
    assert report["sections"][0]["name"] == ".text"


def test_analyzes_pe32(tmp_path):
    path = tmp_path / "sample32.exe"
    make_minimal_pe(path, machine=0x14C, magic=0x10B)
    report = analyze_pe(path)
    assert report["optional_header"] == "PE32"
    assert report["architecture"] == "x86"


def test_rejects_mz_file_without_pe_signature(tmp_path):
    path = tmp_path / "fake.exe"
    path.write_bytes(b"MZ" + b"\0" * 128)
    with pytest.raises(PEFormatError, match="PE signature"):
        analyze_pe(path)


def test_rejects_non_pe_file(tmp_path):
    path = tmp_path / "bad.bin"
    path.write_bytes(b"not a PE")
    with pytest.raises(PEFormatError, match="MZ"):
        analyze_pe(path)
