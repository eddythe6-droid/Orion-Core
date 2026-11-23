import pytest

from orion_core.capability import CapabilityInventory, SCHEMA_VERSION
from orion_core.evidence import EvidenceRecord


def record(claim_id="GFX-001", **overrides):
    values = {
        "claim_id": claim_id,
        "subsystem": "graphics",
        "claim": "A documented Windows PC graphics capability",
        "platform": "windows_pc",
        "classification": "pc_only",
        "status": "confirmed_fact",
        "confidence": "high",
        "checked_on": "2026-11-23",
        "source_url": "https://learn.microsoft.com/en-us/windows/win32/direct3d12/direct3d-12-graphics",
        "source_title": "Direct3D 12",
    }
    values.update(overrides)
    return EvidenceRecord(**values)


def test_inventory_exports_version_and_platform_assessments():
    data = CapabilityInventory([record()]).to_dict()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["record_count"] == 1
    assert data["records"][0]["support"] == {
        "windows_pc": "documented",
        "xbox": "not_documented_for_target",
    }


def test_unknown_evidence_remains_unknown_for_both_targets():
    unknown = record(
        platform="unknown",
        classification="unknown",
        status="unknown",
        source_url=None,
    )
    item = CapabilityInventory([unknown]).to_dict()["records"][0]
    assert item["support"] == {"windows_pc": "unknown", "xbox": "unknown"}


def test_duplicate_claim_ids_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        CapabilityInventory([record(), record()])


def test_subsystem_filter_returns_independent_inventory():
    inventory = CapabilityInventory([record(), record("IO-001", subsystem="file_io")])
    graphics = inventory.for_subsystem("graphics")
    assert len(graphics.records) == 1
    assert graphics.records[0].claim_id == "GFX-001"
