import struct

import pytest

from orion_core.xvd_inspector import (
    HEADER_SIZE,
    XVC_INFO_FIXED_SIZE,
    XVDFormatError,
    inspect_xvd_file,
)


def _write_guid(buf, offset, value):
    import uuid
    buf[offset:offset + 16] = uuid.UUID(value).bytes_le


def _make_xvc(
    path, *, content_type=1, version=2, region_count=1,
    manifest_length_override=None, integrity_enabled=False,
    embedded_length=0, user_data_length=0, mutable_data_pages=0,
):
    info = bytearray(XVC_INFO_FIXED_SIZE)
    _write_guid(info, 0x00, "12345678-1234-5678-9abc-def012345678")
    _write_guid(info, 0x10, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    description = "Orion test package".encode("utf-16le")
    info[0xC10:0xC10 + len(description)] = description
    struct.pack_into("<I", info, 0xD10, version)
    struct.pack_into("<I", info, 0xD14, region_count)
    struct.pack_into("<H", info, 0xD1E, 1)
    struct.pack_into("<I", info, 0xD3C, 1 if version >= 1 else 0)
    struct.pack_into("<I", info, 0xD50, 1 if version >= 2 else 0)
    struct.pack_into("<I", info, 0xD24, 0x40000005)
    struct.pack_into("<Q", info, 0xD28, 0x4000)

    region = bytearray(0x80)
    struct.pack_into("<I", region, 0x00, 0x40000005)
    struct.pack_into("<H", region, 0x04, 0xFFFF)
    struct.pack_into("<I", region, 0x08, 0x11)
    struct.pack_into("<I", region, 0x0C, 0)
    region_description = "XVC-HD".encode("utf-16le")
    region[0x10:0x10 + len(region_description)] = region_description
    struct.pack_into("<Q", region, 0x50, 0x4000)
    struct.pack_into("<Q", region, 0x58, 0x1C)
    struct.pack_into("<Q", region, 0x60, 0x1122334455667788)

    segment = struct.pack("<IQ", 7, 0x1122334455667788)
    specifier = bytearray(0x188)
    struct.pack_into("<I", specifier, 0, 0x40000005)
    key = "RegionName".encode("utf-16le")
    value = "Primary".encode("utf-16le")
    specifier[0x08:0x08 + len(key)] = key
    specifier[0x88:0x88 + len(value)] = value

    manifest = bytes(info)
    if version >= 1:
        manifest += bytes(region) * region_count + segment
    if version >= 2:
        manifest += bytes(specifier)
    if manifest_length_override is not None:
        declared_manifest_length = manifest_length_override
    else:
        declared_manifest_length = len(manifest)

    header = bytearray(HEADER_SIZE)
    header[0x200:0x208] = b"msft-xvd"
    # Fixtures are plaintext; data-integrity layout can be toggled independently.
    volume_flags = 0x02 | (0 if integrity_enabled else 0x04)
    struct.pack_into("<I", header, 0x208, volume_flags)
    struct.pack_into("<I", header, 0x20C, 3)
    struct.pack_into("<Q", header, 0x218, 0x1000)
    _write_guid(header, 0x220, "01010101-0202-0303-0404-050505050505")
    _write_guid(header, 0x230, "11111111-2222-3333-4444-555555555555")
    struct.pack_into("<I", header, 0x280, 0)
    struct.pack_into("<I", header, 0x284, content_type)
    struct.pack_into("<I", header, 0x288, embedded_length)
    struct.pack_into("<I", header, 0x28C, user_data_length)
    struct.pack_into("<I", header, 0x290, declared_manifest_length)
    struct.pack_into("<I", header, 0x294, 0)
    struct.pack_into("<I", header, 0x298, 0xAA000)
    header[0x470] = mutable_data_pages
    _write_guid(header, 0x39C, "aaaaaaaa-1111-2222-3333-444444444444")
    _write_guid(header, 0x3AC, "bbbbbbbb-1111-2222-3333-444444444444")

    page = 0x1000
    page_count = lambda size: (size + page - 1) // page if size else 0
    manifest_pages = page_count(declared_manifest_length)
    if integrity_enabled:
        hashed_pages = page_count(0x1000) + page_count(user_data_length) + manifest_pages
        hash_pages = (hashed_pages + 169) // 170
    else:
        hash_pages = 0
    manifest_offset = (
        HEADER_SIZE + page_count(embedded_length) * page
        + mutable_data_pages * page + hash_pages * page
        + page_count(user_data_length) * page
    )
    image = bytearray(manifest_offset + len(manifest) + 0x100)
    image[:HEADER_SIZE] = header
    image[manifest_offset:manifest_offset + len(manifest)] = manifest
    path.write_bytes(image)


def test_inspects_xvc_header_and_version_two_manifest(tmp_path):
    package = tmp_path / "sample.xvc"
    _make_xvc(package)

    report = inspect_xvd_file(package)

    assert report["valid_header"] is True
    assert report["container_format"] == "XVC"
    assert report["content_type_name"] == "title"
    assert report["format_version"] == 3
    assert report["encryption_status"] == "disabled_in_header"
    manifest = report["xvc_manifest"]
    assert manifest["parse_status"] == "metadata_parsed"
    assert manifest["description"] == "Orion test package"
    assert manifest["key_id_guids"] == ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]
    assert manifest["region_count"] == 1
    assert manifest["regions"][0]["region_name"] == "header"
    assert manifest["regions"][0]["flag_names"] == ["resident", "present"]
    assert manifest["regions"][0]["file_range_in_bounds"] is True
    assert manifest["update_segments"][0]["page_number"] == 7
    assert manifest["region_specifiers"][0]["key"] == "RegionName"
    assert manifest["region_specifiers"][0]["value"] == "Primary"
    assert report["header_signature_cryptographically_verified"] is False
    assert report["payload_decrypted"] is False



def test_manifest_locator_accounts_for_embedded_xvd_mutable_data_and_hash_pages(tmp_path):
    package = tmp_path / "integrity-enabled.xvc"
    _make_xvc(
        package,
        integrity_enabled=True,
        embedded_length=0x1000,
        user_data_length=0x1000,
        mutable_data_pages=2,
    )

    report = inspect_xvd_file(package)

    assert report["layout"]["embedded_xvd_offset"] == 0x3000
    assert report["layout"]["mutable_data_offset"] == 0x4000
    assert report["layout"]["hash_tree_offset"] == 0x6000
    assert report["layout"]["hash_tree_pages_calculated"] == 1
    assert report["layout"]["user_data_offset"] == 0x7000
    assert report["layout"]["xvc_info_offset"] == 0x8000
    assert report["xvc_manifest"]["parse_status"] == "metadata_parsed"

def test_xvc_manifest_reports_region_consistency_observations(tmp_path):
    package = tmp_path / "overlapping-regions.xvc"
    _make_xvc(package, region_count=2)

    image = bytearray(package.read_bytes())
    second_region = HEADER_SIZE + XVC_INFO_FIXED_SIZE + 0x80
    # Keep the same region ID, overlap the first range, and reference a
    # key slot beyond the single declared key ID.
    struct.pack_into("<H", image, second_region + 0x04, 5)
    struct.pack_into("<Q", image, second_region + 0x50, 0x4010)
    package.write_bytes(image)

    report = inspect_xvd_file(package)
    diagnostics = report["xvc_manifest"]["region_diagnostics"]

    assert diagnostics["duplicate_region_id_count"] == 1
    assert diagnostics["key_reference_out_of_range_count"] == 1
    assert diagnostics["regions_overlapping_another_region_count"] == 1
    assert diagnostics["region_file_range_out_of_bounds_count"] == 0
    assert diagnostics["initial_play_region_declared"] is True
    assert diagnostics["preview_region_declared"] is None
    assert "not independently proven corruption" in diagnostics["interpretation"]


def test_non_xvc_xvd_header_does_not_parse_xvc_manifest(tmp_path):
    package = tmp_path / "sample.xvd"
    _make_xvc(package, content_type=0, version=0, region_count=0)

    report = inspect_xvd_file(package)

    assert report["container_format"] == "XVD"
    assert report["xvc_content_type"] is False
    assert report["xvc_manifest"] is None


def test_rejects_truncated_xvd_header(tmp_path):
    package = tmp_path / "truncated.xvc"
    package.write_bytes(b"msft-xvd" + bytes(32))

    with pytest.raises(XVDFormatError, match="smaller"):
        inspect_xvd_file(package)


def test_rejects_missing_xvd_magic(tmp_path):
    package = tmp_path / "not-xvd.bin"
    package.write_bytes(bytes(HEADER_SIZE))

    with pytest.raises(XVDFormatError, match="magic"):
        inspect_xvd_file(package)


def test_manifest_table_bounds_are_reported_without_losing_header(tmp_path):
    package = tmp_path / "bad-manifest.xvc"
    _make_xvc(package, region_count=500, manifest_length_override=XVC_INFO_FIXED_SIZE)

    report = inspect_xvd_file(package)

    assert report["valid_header"] is True
    assert report["xvc_manifest"]["parse_status"] == "malformed_or_truncated_manifest"
    assert "region-header table" in report["xvc_manifest"]["error"]


def test_game_inspector_integrates_xvc_metadata_and_summary(tmp_path):
    from orion_core.game_inspector import inspect_game_path

    package = tmp_path / "title.xvc"
    _make_xvc(package)
    report = inspect_game_path(package)

    assert report["source_kind"] == "xvc_package"
    assert report["xvd_summary"]["xvc_packages"] == 1
    assert report["xvd_summary"]["xvc_regions_parsed"] == 1
    assert report["files"][0]["detected_type"] == "xbox_xvc"
    assert report["files"][0]["xvd_metadata"]["xvc_manifest"]["parse_status"] == "metadata_parsed"


def test_game_inspector_detects_xvc_inside_directory(tmp_path):
    from orion_core.game_inspector import inspect_game_path

    package = tmp_path / "Packages" / "title.xvc"
    package.parent.mkdir()
    _make_xvc(package)
    report = inspect_game_path(tmp_path)

    record = next(item for item in report["files"] if item["path"].endswith("title.xvc"))
    assert record["detected_type"] == "xbox_xvc"
    assert record["xvd_metadata"]["container_format"] == "XVC"
