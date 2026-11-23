"""Structured, validated evidence records for compatibility research.

This module stores claims and their provenance. It deliberately does not infer
platform support from missing evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal
from urllib.parse import urlparse

Platform = Literal["windows_pc", "xbox", "both", "unknown"]
Classification = Literal["common", "pc_only", "xbox_only", "extension", "unknown"]
ClaimStatus = Literal["confirmed_fact", "hypothesis", "unknown"]
Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One traceable statement about a platform dependency or capability."""

    claim_id: str
    subsystem: str
    claim: str
    platform: Platform
    classification: Classification
    status: ClaimStatus
    confidence: Confidence
    checked_on: str
    source_url: str | None = None
    source_title: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        allowed = {
            "platform": {"windows_pc", "xbox", "both", "unknown"},
            "classification": {"common", "pc_only", "xbox_only", "extension", "unknown"},
            "status": {"confirmed_fact", "hypothesis", "unknown"},
            "confidence": {"high", "medium", "low"},
        }
        for name, choices in allowed.items():
            if getattr(self, name) not in choices:
                raise ValueError(f"{name} must be one of: {', '.join(sorted(choices))}")
        for name in ("claim_id", "subsystem", "claim"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        try:
            date.fromisoformat(self.checked_on)
        except (TypeError, ValueError) as exc:
            raise ValueError("checked_on must be an ISO date (YYYY-MM-DD)") from exc
        if self.source_url is not None:
            parsed = urlparse(self.source_url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("source_url must be an absolute HTTPS URL")
        if self.status == "confirmed_fact" and not self.source_url:
            raise ValueError("confirmed facts require a source_url")
        if self.status == "unknown" and self.classification != "unknown":
            raise ValueError("unknown claims must use classification='unknown'")

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-serializable representation."""
        return asdict(self)


def compare_support(record: EvidenceRecord, target: Platform) -> str:
    """Return a conservative support label for a target platform."""
    if record.status == "unknown" or record.classification == "unknown":
        return "unknown"
    if target == "unknown":
        return "unknown"
    if record.platform == "both" or record.platform == target:
        if record.classification in ("common", "extension"):
            return "documented"
        if record.classification == "pc_only" and target == "windows_pc":
            return "documented"
        if record.classification == "xbox_only" and target == "xbox":
            return "documented"
    if record.classification == "pc_only" and target == "xbox":
        return "not_documented_for_target"
    if record.classification == "xbox_only" and target == "windows_pc":
        return "not_documented_for_target"
    return "unknown"
