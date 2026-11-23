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
