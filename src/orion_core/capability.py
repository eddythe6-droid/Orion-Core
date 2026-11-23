"""Machine-readable platform capability inventory.

The inventory is evidence-backed: missing claims remain unknown and are never
converted into assumed compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from orion_core.evidence import EvidenceRecord, compare_support

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class CapabilityInventory:
    """A stable, serializable collection of platform evidence."""

    records: tuple[EvidenceRecord, ...]

    def __init__(self, records: Iterable[EvidenceRecord] = ()) -> None:
        materialized = tuple(records)
        ids = [record.claim_id for record in materialized]
        if len(ids) != len(set(ids)):
            raise ValueError("claim_id values must be unique within an inventory")
        object.__setattr__(self, "records", materialized)

    def to_dict(self) -> dict:
        """Export evidence and conservative support assessments as JSON data."""
        return {
            "schema_version": SCHEMA_VERSION,
            "record_count": len(self.records),
            "records": [
                {
                    **record.to_dict(),
                    "support": {
                        "windows_pc": compare_support(record, "windows_pc"),
                        "xbox": compare_support(record, "xbox"),
                    },
                }
                for record in self.records
            ],
        }

    def for_subsystem(self, subsystem: str) -> "CapabilityInventory":
        """Return a new inventory containing only one named subsystem."""
        return CapabilityInventory(
            record for record in self.records if record.subsystem == subsystem
        )

ASSESSMENT_SCHEMA_VERSION = "1.0"


def assess_compatibility(
    inventory: CapabilityInventory,
    target: str,
    subsystem: str | None = None,
) -> dict:
    """Build a conservative, evidence-linked assessment for one target.

    This assesses documented platform contracts only. It does not claim that
    a particular game's implementation is compatible or that hardware has
    passed runtime validation.
    """
    if target not in {"windows_pc", "xbox"}:
        raise ValueError("target must be 'windows_pc' or 'xbox'")

    selected = inventory.for_subsystem(subsystem) if subsystem else inventory
    items = []
    counts = {
        "compatible": 0,
        "adaptable": 0,
        "platform_specific": 0,
        "unknown": 0,
    }

    for record in selected.records:
        support = compare_support(record, target)
        if record.status != "confirmed_fact" or record.confidence == "low" or support == "unknown":
            status = "unknown"
            reason = "Evidence is incomplete, unconfirmed, or not documented for this target."
        elif support == "not_documented_for_target":
            status = "platform_specific"
            reason = "The documented capability is not available as a contract for this target."
        elif record.classification == "extension":
            status = "adaptable"
            reason = "A shared or related contract exists, but platform-specific adaptation is documented."
        else:
            status = "compatible"
            reason = "A confirmed platform contract is documented for this target."

        counts[status] += 1
        items.append({
            "claim_id": record.claim_id,
            "subsystem": record.subsystem,
            "status": status,
            "support": support,
            "reason": reason,
            "claim": record.claim,
            "confidence": record.confidence,
            "source_url": record.source_url,
            "source_title": record.source_title,
            "notes": record.notes,
        })

    return {
        "schema_version": ASSESSMENT_SCHEMA_VERSION,
        "target": target,
        "subsystem": subsystem,
        "scope": "documented_platform_contracts_only",
        "hardware_validation": "not_performed",
        "record_count": len(items),
        "summary": counts,
        "assessments": items,
    }
