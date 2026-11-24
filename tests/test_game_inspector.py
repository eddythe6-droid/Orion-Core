import json
import struct
import zipfile

import pytest

from orion_core.game_inspector import GameInspectionError, inspect_game_path, save_inspection_report


def test_inspects_directory_and_detects_signatures(tmp_path):
    (tmp_path / "game.exe").write_bytes(b"MZ" + b"\x00" * 20)
    (tmp_path / "texture.bin").write_bytes(b"DDS " + b"\x00" * 20)
    report = inspect_game_path(tmp_path, hash_files=True)
    assert report["files_inspected"] == 2
    by_name = {item["path"]: item for item in report["files"]}
    assert by_name["game.exe"]["detected_type"] == "pe_dos_header"
    assert by_name["texture.bin"]["detected_type"] == "dds"
    assert by_name["game.exe"]["sha256"]


def test_inspects_zip_metadata_without_extracting(tmp_path):
    archive = tmp_path / "disc.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("default.xex", b"XEX2" + b"\x00" * 8)
        stream.writestr("media/texture.dds", b"DDS " + b"\x00" * 8)
    report = inspect_game_path(archive)
    assert report["source_kind"] == "zip_archive"
    assert report["files_inspected"] == 2
    assert all(item["archive_member"] for item in report["files"])
    assert report["extraction_performed"] is False


def test_missing_path_and_bad_limit_are_rejected(tmp_path):
    with pytest.raises(GameInspectionError, match="does not exist"):
        inspect_game_path(tmp_path / "missing")
    with pytest.raises(GameInspectionError, match="positive"):
        inspect_game_path(tmp_path, max_files=0)


def test_file_limit_is_enforced(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"a")
    (tmp_path / "b.bin").write_bytes(b"b")
    with pytest.raises(GameInspectionError, match="file limit"):
        inspect_game_path(tmp_path, max_files=1)


def test_report_is_saved_as_json(tmp_path):
    source = tmp_path / "sample.xex"
    source.write_bytes(b"XEX2" + b"\x00" * 8)
    report = inspect_game_path(source)
    output = save_inspection_report(report, tmp_path / "out" / "report.json")
    assert json.loads(output.read_text(encoding="utf-8"))["tool"] == "orion_game_inspector"


def test_game_inspector_recognizes_iso9660_images(tmp_path):
    import struct

    def both16(value):
        return struct.pack("<H", value) + struct.pack(">H", value)

    def both32(value):
        return struct.pack("<I", value) + struct.pack(">I", value)

    image = bytearray(22 * 2048)
    pvd = memoryview(image)[16 * 2048:17 * 2048]
    pvd[0:7] = b"\x01CD001\x01"
    pvd[80:88] = both32(22)
    pvd[128:132] = both16(2048)
    record = bytearray(34)
    record[0] = 34
    record[2:10] = both32(20)
    record[10:18] = both32(2048)
    record[25] = 2
    record[28:32] = both16(1)
    record[32] = 1
    record[33] = 0
    pvd[156:190] = record
    (tmp_path / "sample.iso").write_bytes(image)
    report = inspect_game_path(tmp_path / "sample.iso")
    assert report["source_kind"] == "iso9660"
    assert report["iso9660"]["format"] == "ISO9660"


def test_game_inspector_prefers_xdvdfs_over_iso9660(tmp_path):
    import struct

    image = bytearray(33 * 2048)
    descriptor = memoryview(image)[32 * 2048:33 * 2048]
    magic = b"MICROSOFT*XBOX*MEDIA"
    descriptor[:20] = magic
    struct.pack_into("<IIQ", descriptor, 0x14, 0, 0, 0)
    descriptor[0x7EC:0x800] = magic
    source = tmp_path / "xbox-game.iso"
    source.write_bytes(image)

    report = inspect_game_path(source)
    assert report["source_kind"] == "xdvdfs"
    assert report["xdvdfs"]["format"] == "XDVDFS"
    assert report["iso9660"] is None


def test_game_inspector_includes_scarlett_assessment_for_valid_pe(tmp_path):
    path = tmp_path / "ordinary.exe"
    data = bytearray(0x400)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 1, 123, 0, 0, 0xF0, 0x22)
    opt = 0x98
    struct.pack_into("<H", data, opt, 0x20B)
    struct.pack_into("<I", data, opt + 16, 0x1000)
    struct.pack_into("<Q", data, opt + 24, 0x140000000)
    struct.pack_into("<I", data, opt + 108, 16)
    struct.pack_into("<H", data, opt + 68, 3)
    sec = opt + 0xF0
    data[sec:sec + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, sec + 8, 0x100, 0x1000, 0x200, 0x200)
    path.write_bytes(data)

    report = inspect_game_path(path)
    record = report["files"][0]
    assert record["pe_analysis"]["architecture"] == "x86_64"
    assert record["scarlett_analysis"]["assessment"] == "x64_pe_candidate_no_specific_gdk_imports"
    assert record["scarlett_analysis"]["authenticity_verified"] is False
    assert record["dependency_analysis"]["module_count"] == 0
    assert record["dependency_analysis"]["compatibility_established"] is False

def test_game_inspector_detects_shader_by_magic_not_extension(tmp_path):
    spirv = tmp_path / "payload.dat"
    spirv.write_bytes(struct.pack("<5I", 0x07230203, 0x00010000, 3, 32, 0))
    report = inspect_game_path(tmp_path)
    record = report["files"][0]
    assert record["shader_analysis"]["format"] == "spirv"
    assert record["shader_analysis"]["extension_format_match"] is True
    assert report["shader_summary"]["files_with_shader_analysis"] == 1
    assert report["shader_summary"]["formats"] == {"spirv": 1}


def test_game_inspector_reports_malformed_shader_extension(tmp_path):
    shader = tmp_path / "broken.spv"
    shader.write_bytes(b"not a shader")
    report = inspect_game_path(tmp_path)
    record = report["files"][0]
    assert record["shader_analysis"]["assessment"] == "unrecognized_or_malformed_shader_container"
    assert record["shader_analysis"]["bytecode_validated"] is False


def test_game_inspector_summarizes_spirv_metadata(tmp_path):
    # OpCapability Shader and OpEntryPoint GLCompute %3 "main".
    name = b"main\\x00"
    name += b"\\x00" * ((-len(name)) % 4)
    name_word = struct.unpack("<I", name)[0]
    words = [
        0x07230203, 0x00010000, 1, 16, 0,
        (2 << 16) | 17, 1,
        (4 << 16) | 15, 5, 3, name_word,
    ]
    (tmp_path / "compute.spv").write_bytes(struct.pack("<" + "I" * len(words), *words))
    report = inspect_game_path(tmp_path)
    summary = report["shader_summary"]
    assert summary["spirv_capability_occurrences"] == {"1": 1}
    assert summary["spirv_entry_point_count"] == 1
