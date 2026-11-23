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


def test_compatibility_assessment_maps_documented_common_contract_to_compatible():
    from orion_core.capability import assess_compatibility

    shared = record(
        platform="both",
        classification="common",
        claim="Shared API",
    )
    report = assess_compatibility(CapabilityInventory([shared]), "windows_pc")
    assert report["scope"] == "documented_platform_contracts_only"
    assert report["hardware_validation"] == "not_performed"
    assert report["summary"]["compatible"] == 1
    assert report["assessments"][0]["claim_id"] == shared.claim_id
    assert report["assessments"][0]["status"] == "compatible"


def test_compatibility_assessment_marks_extensions_as_adaptable():
    from orion_core.capability import assess_compatibility

    extension = record(
        platform="both",
        classification="extension",
        claim="Shared API with platform extensions",
    )
    report = assess_compatibility(CapabilityInventory([extension]), "xbox")
    assert report["summary"]["adaptable"] == 1
    assert report["assessments"][0]["status"] == "adaptable"


def test_compatibility_assessment_preserves_platform_specific_and_unknown():
    from orion_core.capability import assess_compatibility

    pc_only = record()
    unknown = record(
        claim_id="UNKNOWN-001",
        platform="unknown",
        classification="unknown",
        status="unknown",
        source_url=None,
        confidence="low",
    )
    report = assess_compatibility(CapabilityInventory([pc_only, unknown]), "xbox")
    assert report["summary"]["platform_specific"] == 1
    assert report["summary"]["unknown"] == 1
    assert [item["status"] for item in report["assessments"]] == [
        "platform_specific", "unknown"
    ]


def test_compatibility_assessment_validates_target_and_filters_subsystem():
    from orion_core.capability import assess_compatibility

    inventory = CapabilityInventory([
        record(),
        record("IO-001", subsystem="file_io"),
    ])
    report = assess_compatibility(inventory, "windows_pc", subsystem="file_io")
    assert report["record_count"] == 1
    assert report["assessments"][0]["claim_id"] == "IO-001"
    with pytest.raises(ValueError, match="target"):
        assess_compatibility(inventory, "linux")
