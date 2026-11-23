import struct

import pytest

from orion_core.stfs import STFSError, inspect_stfs, inspect_svod_directory


def make_header(path, *, magic=b"LIVE", volume=1, content=0x7000):
    data = bytearray(0x1720)
    data[:4] = magic
    struct.pack_into(">I", data, 0x340, 0x971A)
    struct.pack_into(">I", data, 0x344, content)
    struct.pack_into(">I", data, 0x348, 2)
    struct.pack_into(">Q", data, 0x34C, 123456789)
    struct.pack_into(">I", data, 0x354, 0x11223344)
    struct.pack_into(">I", data, 0x360, 0x4D530001)
    data[0x364:0x368] = bytes((2, 0, 1, 2))
    struct.pack_into(">I", data, 0x39D, 2)
    struct.pack_into(">Q", data, 0x3A1, 999)
    struct.pack_into(">I", data, 0x3A9, volume)
    data[0x411:0x419] = "Game".encode("utf-16-be")
    data[0x1611:0x161B] = "Studio".encode("utf-16-be")
    data[0x1691:0x169B] = "Title".encode("utf-16-be")
    path.write_bytes(data)


@pytest.mark.parametrize("magic", [b"CON ", b"LIVE", b"PIRS"])
def test_reads_public_xcontent_metadata(tmp_path, magic):
    package = tmp_path / "content"
    make_header(package, magic=magic)
    result = inspect_stfs(package)
    assert result["signature_type"] == magic.decode("ascii").strip()
    assert result["content_type_name"] == "games_on_demand"
    assert result["title_id"] == 0x4D530001
    assert result["container_format"] == "SVOD"
    assert result["display_name"] == "Game"
    assert result["signature_verified"] is False
    assert result["payload_read"] is False


def test_rejects_non_package_and_truncated_header(tmp_path):
    package = tmp_path / "bad"
    package.write_bytes(b"NOPE")
    with pytest.raises(STFSError, match="signature"):
        inspect_stfs(package)
    package.write_bytes(b"LIVE" + bytes(20))
    with pytest.raises(STFSError, match="truncated"):
        inspect_stfs(package)


def test_identifies_god_sibling_layout_without_reading_payload(tmp_path):
    header = tmp_path / "ABCDEF"
    make_header(header)
    data_dir = tmp_path / "ABCDEF.data"
    data_dir.mkdir()
    (data_dir / "Data0000").write_bytes(b"x" * 32)
    (data_dir / "Data0001").write_bytes(b"y" * 16)
    report = inspect_svod_directory(tmp_path)
    assert len(report["containers"]) == 1
    item = report["containers"][0]
    assert item["data_file_count_observed"] == 2
    assert item["package_metadata"]["title_id"] == 0x4D530001
    assert report["payload_reassembled"] is False
