from orion_core.platform_catalog import load_platform_inventory
from orion_core.evidence import compare_support


def test_curated_catalog_has_unique_traceable_records():
    inventory = load_platform_inventory()
    assert len(inventory.records) >= 9
    assert len({item.claim_id for item in inventory.records}) == len(inventory.records)
    assert all(item.source_url and item.source_url.startswith("https://") for item in inventory.records)


def test_catalog_preserves_unknown_game_specific_usage_as_out_of_scope():
    inventory = load_platform_inventory()
    assert all("GTA VI" not in item.claim for item in inventory.records)


def test_catalog_exposes_xbox_graphics_extension_without_promoting_it_to_pc():
    records = {item.claim_id: item for item in load_platform_inventory().records}
    assert compare_support(records["GDK-GFX-001"], "xbox") == "documented"
    assert compare_support(records["GDK-GFX-001"], "windows_pc") == "not_documented_for_target"


def test_pc_graphics_contracts_are_not_claimed_as_xbox_facts():
    records = {item.claim_id: item for item in load_platform_inventory().records}
    for claim_id in ("D3D12-QUEUE-001", "D3D12-MEM-001", "D3D12-BIND-001", "D3D12-FEATURE-001"):
        assert records[claim_id].platform == "windows_pc"
        assert compare_support(records[claim_id], "windows_pc") == "documented"
        assert compare_support(records[claim_id], "xbox") == "not_documented_for_target"


def test_catalog_tracks_shared_input_save_and_file_apis():
    records = {item.claim_id: item for item in load_platform_inventory().records}
    for claim_id, subsystem in (
        ("GDK-INPUT-001", "input"),
        ("GDK-SAVE-001", "save_data"),
        ("GDK-FILE-001", "file_io"),
    ):
        record = records[claim_id]
        assert record.subsystem == subsystem
        assert record.platform == "both"
        assert compare_support(record, "windows_pc") == "documented"
        assert compare_support(record, "xbox") == "documented"


def test_catalog_tracks_audio_api_extensions_and_xma_boundary():
    records = {item.claim_id: item for item in load_platform_inventory().records}
    audio = records["GDK-AUDIO-001"]
    assert audio.subsystem == "audio"
    assert audio.platform == "both"
    assert audio.classification == "extension"
    assert compare_support(audio, "windows_pc") == "documented"
    assert compare_support(audio, "xbox") == "documented"

    xma = records["GDK-AUDIO-XMA-001"]
    assert xma.platform == "xbox"
    assert compare_support(xma, "xbox") == "documented"
    assert compare_support(xma, "windows_pc") == "not_documented_for_target"


def test_catalog_tracks_network_api_and_gdk_lifecycle_contracts():
    records = {item.claim_id: item for item in load_platform_inventory().records}
    shared = records["GDK-NET-001"]
    assert shared.subsystem == "networking"
    assert shared.platform == "both"
    assert compare_support(shared, "windows_pc") == "documented"
    assert compare_support(shared, "xbox") == "documented"

    udp = records["GDK-NET-UDP-001"]
    assert udp.platform == "xbox"
    assert udp.classification == "extension"
    assert compare_support(udp, "xbox") == "documented"
    assert compare_support(udp, "windows_pc") == "not_documented_for_target"
