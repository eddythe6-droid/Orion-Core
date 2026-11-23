import struct

import pytest

from orion_core.iso9660 import ISO9660Error, inspect_iso9660


def both16(value):
    return struct.pack("<H", value) + struct.pack(">H", value)


def both32(value):
    return struct.pack("<I", value) + struct.pack(">I", value)


def directory_record(extent, size, name, is_dir=False):
    encoded = name if isinstance(name, bytes) else name.encode("ascii")
    record_len = 33 + len(encoded) + (1 if len(encoded) % 2 == 0 else 0)
    record = bytearray(record_len)
    record[0] = record_len
    record[2:10] = both32(extent)
    record[10:18] = both32(size)
    record[25] = 2 if is_dir else 0
    record[28:32] = both16(1)
    record[32] = len(encoded)
    record[33:33 + len(encoded)] = encoded
    return bytes(record)


def make_iso(path):
    image = bytearray(24 * 2048)
    pvd = memoryview(image)[16 * 2048:17 * 2048]
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[40:72] = b"ORION_TEST".ljust(32, b" ")
    pvd[80:88] = both32(24)
    pvd[128:132] = both16(2048)
    root = directory_record(20, 2048, b"\x00", True)
    pvd[156:156 + len(root)] = root
    directory = bytearray(2048)
    records = [
        directory_record(20, 2048, b"\x00", True),
        directory_record(20, 2048, b"\x01", True),
        directory_record(21, 1234, "GAME.XEX;1"),
        directory_record(22, 2048, "MEDIA", True),
    ]
    cursor = 0
    for record in records:
        directory[cursor:cursor + len(record)] = record
        cursor += len(record)
    image[20 * 2048:21 * 2048] = directory
    child = bytearray(2048)
    child_records = [
        directory_record(22, 2048, b"\x00", True),
        directory_record(20, 2048, b"\x01", True),
        directory_record(23, 512, "TEXTURE.DDS;1"),
    ]
    cursor = 0
    for record in child_records:
        child[cursor:cursor + len(record)] = record
        cursor += len(record)
    image[22 * 2048:23 * 2048] = child
    path.write_bytes(image)


def test_reads_iso_volume_and_recursive_directory_tree(tmp_path):
    image = tmp_path / "game.iso"
    make_iso(image)
    report = inspect_iso9660(image)
    assert report["format"] == "ISO9660"
    assert report["volume_identifier"] == "ORION_TEST"
    paths = {item["path"] for item in report["entries"]}
    assert "GAME.XEX" in paths
    assert "MEDIA/TEXTURE.DDS" in paths
    assert report["extraction_performed"] is False


def test_rejects_non_iso_image(tmp_path):
    image = tmp_path / "bad.iso"
    image.write_bytes(b"not an ISO" * 100)
    with pytest.raises(ISO9660Error, match="descriptor not found"):
        inspect_iso9660(image)


def test_entry_limit_is_enforced(tmp_path):
    image = tmp_path / "game.iso"
    make_iso(image)
    with pytest.raises(ISO9660Error, match="entry limit"):
        inspect_iso9660(image, max_entries=1)
