import pytest

from orion_core.evidence import EvidenceRecord, compare_support


def make_record(**overrides):
    values = {
        "claim_id": "GDK-CORE-001",
        "subsystem": "file_io",
        "claim": "Win32 file I/O is part of the documented common GDK model",
        "platform": "both",
        "classification": "common",
        "status": "confirmed_fact",
        "confidence": "high",
        "checked_on": "2026-11-23",
        "source_url": "https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction",
        "source_title": "Microsoft GDK overview",
    }
    values.update(overrides)
    return EvidenceRecord(**values)


def test_confirmed_fact_serializes_with_provenance():
    record = make_record()
    assert record.to_dict()["claim_id"] == "GDK-CORE-001"
    assert record.to_dict()["source_url"].startswith("https://")


def test_confirmed_fact_requires_source():
    with pytest.raises(ValueError, match="require a source_url"):
        make_record(source_url=None)


def test_rejects_non_https_source():
    with pytest.raises(ValueError, match="HTTPS"):
        make_record(source_url="http://example.com")


def test_unknown_cannot_claim_platform_classification():
    with pytest.raises(ValueError, match="classification='unknown'"):
        make_record(status="unknown", classification="common", source_url=None)


def test_unknown_support_stays_unknown():
    record = make_record(
        platform="unknown",
        classification="unknown",
        status="unknown",
        source_url=None,
    )
    assert compare_support(record, "windows_pc") == "unknown"


def test_pc_only_claim_is_not_promoted_to_xbox_support():
    record = make_record(
        platform="windows_pc",
        classification="pc_only",
    )
    assert compare_support(record, "windows_pc") == "documented"
    assert compare_support(record, "xbox") == "not_documented_for_target"


def test_invalid_date_is_rejected():
    with pytest.raises(ValueError, match="ISO date"):
        make_record(checked_on="yesterday")
