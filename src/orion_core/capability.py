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
