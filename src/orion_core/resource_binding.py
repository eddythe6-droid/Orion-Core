"""Conservative resource-binding requirement checks for D3D12 probe data."""
from __future__ import annotations

from typing import Any


def _tier(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value if 1 <= value <= 3 else None
    if not isinstance(value, str):
        return None
    normalized = value.removeprefix("tier_")
    if normalized not in {"1", "2", "3"}:
        return None
    return int(normalized)


def assess_binding_requirements(required_tier: str | int | None, adapter: dict[str, Any]) -> dict[str, Any]:
    reported = adapter.get("resource_binding_tier")
    required = _tier(required_tier)
    actual = _tier(reported)
    if required is None or actual is None:
        status, reason = "unknown", "required or reported resource-binding tier is unavailable or unrecognized"
    elif actual >= required:
        status, reason = "satisfied", "reported binding tier meets the declared minimum"
    else:
        status, reason = "not_satisfied", "reported binding tier is below the declared minimum"
    return {
        "schema_version": 1, "adapter": adapter.get("name", "unknown"),
        "required_tier": required_tier, "reported_tier": reported,
        "status": status, "reason": reason,
        "limitations": [
            "Does not validate root signatures, descriptor heap layouts, descriptor counts, or shader resource declarations.",
            "Does not create descriptor heaps or bind resources on a native command list.",
            "Windows D3D12 binding tier does not establish Xbox D3D12.x compatibility.",
        ],
    }
