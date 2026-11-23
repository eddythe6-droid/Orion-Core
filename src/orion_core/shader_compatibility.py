"""Conservative shader-feature assessment from native D3D12 probe records."""
from __future__ import annotations

from typing import Any

FEATURE_FIELDS = {
    "wave_ops": "wave_ops",
    "int64_shader_ops": "int64_shader_ops",
    "raytracing": "raytracing_tier",
    "mesh_shaders": "mesh_shader_tier",
    "sampler_feedback": "sampler_feedback_tier",
}


def _tier(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, str) or value in {"", "unknown", "not_supported"}:
        return None
    try:
        return tuple(int(part) for part in value.split("_"))
    except ValueError:
        return None


def assess_shader_requirements(requirements: dict[str, Any], adapter: dict[str, Any]) -> dict[str, Any]:
    """Compare declared requirements with reported features; missing stays unknown.

    Boolean requirements are only evaluated when the probe returned a boolean.
    Tier requirements use numeric tuple comparison and never infer from GPU model.
    """
    results = []
    for feature, required in requirements.items():
        field = FEATURE_FIELDS.get(feature)
        if field is None:
            results.append({"feature": feature, "status": "unknown", "reason": "requirement feature is not recognized"})
            continue
        actual = adapter.get(field)
        if feature in {"wave_ops", "int64_shader_ops"}:
            if not isinstance(required, bool) or not isinstance(actual, bool):
                status, reason = "unknown", "required or reported boolean value is unavailable"
            elif not required:
                status, reason = "satisfied", "feature is not required"
            elif actual:
                status, reason = "satisfied", "probe reports feature support"
            else:
                status, reason = "not_satisfied", "probe reports feature unavailable"
        else:
            req_tier, actual_tier = _tier(required), _tier(actual)
            if req_tier is None or actual_tier is None:
                status, reason = "unknown", "required or reported tier is unavailable"
            elif actual_tier >= req_tier:
                status, reason = "satisfied", "reported tier meets declared minimum"
            else:
                status, reason = "not_satisfied", "reported tier is below declared minimum"
        results.append({"feature": feature, "required": required, "reported": actual,
                        "status": status, "reason": reason})
    statuses = {item["status"] for item in results}
    overall = ("not_satisfied" if "not_satisfied" in statuses else
               "unknown" if "unknown" in statuses else "satisfied")
    return {
        "schema_version": 1,
        "adapter": adapter.get("name", "unknown"),
        "overall": overall,
        "results": results,
        "limitations": [
            "Assesses declared feature requirements only, not shader bytecode validity.",
            "Does not compile shaders or create a native pipeline state object.",
            "Windows D3D12 probe results do not establish Xbox D3D12.x compatibility.",
        ],
    }
