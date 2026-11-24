import struct

from orion_core.scarlett import inspect_scarlett_pe


def make_pe(path, imports=()):
    data = bytearray(0x800)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 1, 0, 0, 0, 0xF0, 0x22)
    opt = 0x98
    struct.pack_into("<H", data, opt, 0x20B)
    struct.pack_into("<I", data, opt + 16, 0x1000)
    struct.pack_into("<Q", data, opt + 24, 0x140000000)
    struct.pack_into("<I", data, opt + 108, 16)
    struct.pack_into("<H", data, opt + 68, 3)
    sec = opt + 0xF0
    data[sec:sec + 8] = b".rdata\0\0"
    struct.pack_into("<IIII", data, sec + 8, 0x500, 0x1000, 0x600, 0x200)
    if imports:
        # Import directory at RVA 0x1000; first descriptor points to DLL name RVA 0x1080.
        struct.pack_into("<II", data, opt + 112 + 8, 0x1000, 40)
        struct.pack_into("<IIIII", data, 0x200, 0x1100, 0, 0, 0x1080, 0x1120)
        cursor = 0x280
        for name in imports:
            raw = name.encode("ascii") + b"\0"
            data[cursor:cursor + len(raw)] = raw
            cursor += len(raw)
        struct.pack_into("<IIIII", data, 0x214, 0, 0, 0, 0, 0)
    path.write_bytes(data)


def test_identifies_x64_pe_with_scarlett_import_hint(tmp_path):
    path = tmp_path / "game.exe"
    make_pe(path, ["d3d12_xs.dll"])
    result = inspect_scarlett_pe(path)
    assert result["assessment"] == "xbox_series_gdk_candidate"
    assert result["architecture_matches_xbox_series_cpu"] is True
    assert result["authenticity_verified"] is False
    assert result["execution_performed"] is False


def test_x64_pe_without_gdk_hints_is_not_called_scarlett(tmp_path):
    path = tmp_path / "ordinary.exe"
    make_pe(path)
    result = inspect_scarlett_pe(path)
    assert result["assessment"] == "x64_pe_candidate_no_specific_gdk_imports"



def test_reports_xbox_series_delay_load_dependency_evidence(tmp_path):
    path = tmp_path / "delayed.exe"
    make_pe(path)
    data = bytearray(path.read_bytes())
    opt = 0x98
    struct.pack_into("<II", data, opt + 112 + 13 * 8, 0x1000, 64)
    struct.pack_into("<IIIIIIII", data, 0x200, 1, 0x1080, 0, 0, 0, 0, 0, 0)
    data[0x280:0x288] = b"xmem.dll\x00"
    path.write_bytes(data)

    result = inspect_scarlett_pe(path)
    assert result["assessment"] == "xbox_series_gdk_candidate"
    assert result["delay_load_module_count"] == 1
    assert result["module_evidence"] == [{
        "module": "xmem.dll",
        "category": "xbox_memory_api",
        "load_kind": "delay_load_import",
        "imported_symbol_count": 0,
        "imported_symbols": [],
        "symbol_inventory_truncated": False,
    }]
