import struct

import pytest

from orion_core.xdvdfs import XDVDFSError, inspect_xdvdfs


MAGIC = b"MICROSOFT*XBOX*MEDIA"


def make_entry(name, sector, size, attributes=0x20, left=0, right=0):
    encoded = name.encode("ascii")
    raw = bytearray(14 + len(encoded))
    struct.pack_into("<HHII", raw, 0, left, right, sector, size)
    raw[12] = attributes
    raw[13] = len(encoded)
    raw[14:] = encoded
    raw.extend(b"\xff" * ((-len(raw)) % 4))
    return bytes(raw)


def make_xiso(path, *, rebuilt=False):
    image = bytearray(32 * 2048 + 16 * 2048)
    base = 0
    descriptor_offset = 0 if rebuilt else 32 * 2048
    root_sector = 40
    root_size = 2048
    descriptor = memoryview(image)[descriptor_offset:descriptor_offset + 2048]
    descriptor[:20] = MAGIC
    struct.pack_into("<IIQ", descriptor, 0x14, root_sector, root_size, 123456789)
    descriptor[0x7EC:0x800] = MAGIC
    root = bytearray(2048)
    file_entry = make_entry("default.xbe", 50, 4096, 0x20)
    dir_entry = make_entry("MEDIA", 42, 2048, 0x10, right=5)
    # The right child is stored at DWORD offset 4 (byte offset 4 * 4).
    root[:len(dir_entry)] = dir_entry
    child_offset = 5 * 4
    root[child_offset:child_offset + len(file_entry)] = file_entry
    image[root_sector * 2048:root_sector * 2048 + root_size] = root
    child = bytearray(2048)
    nested = make_entry("texture.dds", 51, 512, 0x20)
    child[:len(nested)] = nested
    image[42 * 2048:43 * 2048] = child
    path.write_bytes(image)


def test_reads_xdvdfs_volume_and_recursive_entries(tmp_path):
    image = tmp_path / "game.iso"
    make_xiso(image)
    report = inspect_xdvdfs(image)
    assert report["format"] == "XDVDFS"
    assert report["descriptor_sector"] == 32
    paths = {entry["path"] for entry in report["entries"]}
    assert "default.xbe" in paths
    assert "MEDIA/texture.dds" in paths
    assert report["extraction_performed"] is False


def test_accepts_rebuilt_sector_zero_volume(tmp_path):
    image = tmp_path / "rebuilt.xiso"
    make_xiso(image, rebuilt=True)
    report = inspect_xdvdfs(image)
    assert report["descriptor_sector"] == 0
    assert report["volume_base_offset"] == 0


def test_rejects_non_xdvdfs_image(tmp_path):
    image = tmp_path / "bad.iso"
    image.write_bytes(b"not an XDVDFS image" * 200)
    with pytest.raises(XDVDFSError, match="descriptor not found"):
        inspect_xdvdfs(image)


def test_enforces_entry_limit(tmp_path):
    image = tmp_path / "game.iso"
    make_xiso(image)
    with pytest.raises(XDVDFSError, match="entry limit"):
        inspect_xdvdfs(image, max_entries=1)


@pytest.mark.parametrize(
    ("layout", "base"),
    [("XGD2", 0x0FD90000), ("XGD3", 0x02080000), ("XGD1", 0x18300000)],
)
def test_detects_full_disc_partition_offsets(tmp_path, layout, base):
    image = tmp_path / f"{layout.lower()}.iso"
    with image.open("wb") as stream:
        stream.truncate(base + 45 * 2048)
        descriptor = bytearray(2048)
        descriptor[:20] = MAGIC
        struct.pack_into("<IIQ", descriptor, 0x14, 0, 0, 987654321)
        descriptor[0x7EC:0x800] = MAGIC
        stream.seek(base + 32 * 2048)
        stream.write(descriptor)

    report = inspect_xdvdfs(image)
    assert report["disc_layout"] == layout
    assert report["volume_base_offset"] == base
    assert report["descriptor_sector"] == 32
