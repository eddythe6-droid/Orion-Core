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



def make_pe_with_imports(path, *, magic=0x20B, ordinal=False, missing_original=False):
    make_minimal_pe(path, machine=0x8664 if magic == 0x20B else 0x14C, magic=magic)
    data = bytearray(path.read_bytes())
    opt = 0x98
    directory_offset = 112 if magic == 0x20B else 96
    thunk_size = 8 if magic == 0x20B else 4
    thunk_rva = 0x1050
    name_rva = 0x1040
    struct.pack_into("<II", data, opt + directory_offset + 8, 0x1000, 40)
    struct.pack_into("<IIIII", data, 0x200, 0 if missing_original else thunk_rva, 0, 0, name_rva, thunk_rva)
    data[0x240:0x24C] = b"kernel32.dll\0"
    if ordinal:
        value = (0x8000000000000000 if thunk_size == 8 else 0x80000000) | 17
    else:
        value = 0x1060
    data[0x250:0x250 + thunk_size] = value.to_bytes(thunk_size, "little")
    data[0x250 + thunk_size:0x250 + 2 * thunk_size] = b"\0" * thunk_size
    if not ordinal:
        struct.pack_into("<H", data, 0x260, 7)
        data[0x262:0x26D] = b"CreateFileW\0"
    path.write_bytes(data)


def test_reads_named_import_function(tmp_path):
    path = tmp_path / "named.exe"
    make_pe_with_imports(path)
    report = analyze_pe(path)
    assert report["imported_dlls"] == ["kernel32.dll"]
    assert report["imported_functions"][0] == {
        "dll": "kernel32.dll", "kind": "name", "name": "CreateFileW", "hint": 7
    }


def test_reads_ordinal_import(tmp_path):
    path = tmp_path / "ordinal.exe"
    make_pe_with_imports(path, ordinal=True)
    report = analyze_pe(path)
    assert report["imported_functions"][0]["kind"] == "ordinal"
    assert report["imported_functions"][0]["ordinal"] == 17


def test_uses_first_thunk_when_original_first_thunk_is_zero(tmp_path):
    path = tmp_path / "fallback.exe"
    make_pe_with_imports(path, missing_original=True)
    report = analyze_pe(path)
    assert report["imported_functions"][0]["name"] == "CreateFileW"


def test_reads_pe32_named_import(tmp_path):
    path = tmp_path / "named32.exe"
    make_pe_with_imports(path, magic=0x10B)
    report = analyze_pe(path)
    assert report["imported_functions"][0]["name"] == "CreateFileW"


def make_pe_with_delay_import(path, *, rva_based=True):
    make_minimal_pe(path, machine=0x8664 if rva_based else 0x14C,
                    magic=0x20B if rva_based else 0x10B)
    data = bytearray(path.read_bytes())
    opt = 0x98
    directory_offset = 112 if rva_based else 96
    struct.pack_into("<II", data, opt + directory_offset + 13 * 8, 0x1000, 64)
    name_value = 0x1080 if rva_based else 0x401080
    struct.pack_into("<IIIIIIII", data, 0x200, 1 if rva_based else 0,
                     name_value, 0, 0, 0, 0, 0, 0)
    data[0x280:0x28D] = b"delaymod.dll\0"
    path.write_bytes(data)


def test_reads_rva_based_delay_import_module(tmp_path):
    path = tmp_path / "delay-rva.exe"
    make_pe_with_delay_import(path)
    report = analyze_pe(path)
    assert report["delay_import_modules"] == [{
        "dll": "delaymod.dll", "attributes": 1, "rva_based": True
    }]
    assert report["delay_imports_truncated_or_unavailable"] is False


def test_reads_va_based_delay_import_module(tmp_path):
    path = tmp_path / "delay-va.exe"
    make_pe_with_delay_import(path, rva_based=False)
    report = analyze_pe(path)
    assert report["delay_import_modules"][0]["dll"] == "delaymod.dll"
    assert report["delay_import_modules"][0]["rva_based"] is False
