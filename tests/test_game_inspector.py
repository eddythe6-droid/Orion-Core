import json
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
