"""Validation and normalization for native Orion D3D12 probe JSON.

This module does not execute native binaries. It validates reports supplied by
the user and preserves unknown capability values rather than guessing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GPU_PROBE_SCHEMA_VERSION = 1


class ProbeReportError(ValueError):
    """Raised when a native probe report is malformed or unsupported."""


def load_probe_report(path: str | Path) -> dict[str, Any]:
    """Load and validate a JSON report written by orion-d3d12-probe."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeReportError(f"cannot read probe report: {type(exc).__name__}") from exc
    return validate_probe_report(raw)


def validate_probe_report(raw: Any) -> dict[str, Any]:
    """Validate the stable top-level structure and adapter records."""
    if not isinstance(raw, dict):
        raise ProbeReportError("report must be a JSON object")
    if raw.get("schema_version") != GPU_PROBE_SCHEMA_VERSION:
        raise ProbeReportError("unsupported or missing probe schema_version")
    if raw.get("probe") != "orion_d3d12_probe":
        raise ProbeReportError("unexpected probe identifier")
    if not isinstance(raw.get("available"), bool):
        raise ProbeReportError("available must be a boolean")
    adapters = raw.get("adapters")
    if not isinstance(adapters, list):
        raise ProbeReportError("adapters must be a list")
    for index, adapter in enumerate(adapters):
        if not isinstance(adapter, dict):
            raise ProbeReportError(f"adapter {index} must be an object")
        if not isinstance(adapter.get("name"), str):
            raise ProbeReportError(f"adapter {index} is missing a string name")
        if not isinstance(adapter.get("software"), bool):
            raise ProbeReportError(f"adapter {index} software must be a boolean")
        if not isinstance(adapter.get("d3d12_device"), bool):
            raise ProbeReportError(f"adapter {index} d3d12_device must be a boolean")
        for key in ("feature_level", "shader_model", "resource_binding_tier",
                    "raytracing_tier", "mesh_shader_tier", "sampler_feedback_tier"):
            if key in adapter and adapter[key] is not None and not isinstance(adapter[key], str):
                raise ProbeReportError(f"adapter {index} {key} must be a string or null")
    return raw


def summarize_probe_report(report: dict[str, Any]) -> dict[str, Any]:
    """Produce a small comparison-friendly summary without inferred support."""
    validated = validate_probe_report(report)
    adapters = []
    for item in validated["adapters"]:
        adapters.append({
            "name": item["name"],
            "software": item["software"],
            "d3d12_device": item["d3d12_device"],
            "feature_level": item.get("feature_level", "unknown"),
            "shader_model": item.get("shader_model", "unknown"),
            "resource_binding_tier": item.get("resource_binding_tier", "unknown"),
            "raytracing_tier": item.get("raytracing_tier", "unknown"),
            "mesh_shader_tier": item.get("mesh_shader_tier", "unknown"),
            "sampler_feedback_tier": item.get("sampler_feedback_tier", "unknown"),
            "direct_queue_fence_test": item.get("direct_queue_fence_test"),
        })
    return {
        "schema_version": GPU_PROBE_SCHEMA_VERSION,
        "probe": validated["probe"],
        "available": validated["available"],
        "hardware_d3d12_adapters": validated.get("hardware_d3d12_adapters", 0),
        "adapters": adapters,
        "interpretation": {
            "hardware_runtime_validation": True,
            "game_compatibility_established": False,
            "unknown_values_are_not_unsupported": True,
        },
    }



def _version_tuple(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, str) or value in {"", "unknown", "not_supported"}:
        return None
    try:
        parts = tuple(int(part) for part in value.split("_"))
    except ValueError:
        return None
    return parts


def compare_gpu_adapters(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Compare two validated adapter records without inferring game compatibility.

    Version/tier fields are compared numerically only when both are known.
    Boolean feature fields are compared only when both sides reported a bool.
    Raw format masks are compared as bit sets, not decoded into usage claims.
    """
    version_fields = (
        "feature_level", "shader_model", "resource_binding_tier",
        "raytracing_tier", "mesh_shader_tier", "sampler_feedback_tier",
    )
    boolean_fields = (
        "wave_ops", "int64_shader_ops", "expanded_compute_resource_states",
    )
    results: list[dict[str, Any]] = []
    for field in version_fields:
        a, b = left.get(field, "unknown"), right.get(field, "unknown")
        av, bv = _version_tuple(a), _version_tuple(b)
        if a == "not_supported" and b == "not_supported":
            status, relation = "same", "neither reports support"
        elif av is None or bv is None:
            status, relation = "unknown", "one or both values are unknown or not comparable"
        elif av == bv:
            status, relation = "same", "same reported level"
        elif av > bv:
            status, relation = "left_higher", "left reports a higher level"
        else:
            status, relation = "right_higher", "right reports a higher level"
        results.append({"capability": field, "left": a, "right": b,
                        "status": status, "relation": relation})

    for field in boolean_fields:
        a, b = left.get(field), right.get(field)
        if not isinstance(a, bool) or not isinstance(b, bool):
            status, relation = "unknown", "one or both queries did not return a boolean"
        elif a == b:
            status, relation = "same", "same reported value"
        else:
            status, relation = "left_only" if a else "right_only", "reported on one adapter only"
        results.append({"capability": field, "left": a, "right": b,
                        "status": status, "relation": relation})

    for field in ("rgba8_support1", "rgba8_support2"):
        a, b = left.get(field), right.get(field)
        if not isinstance(a, int) or isinstance(a, bool) or not isinstance(b, int) or isinstance(b, bool):
            results.append({"capability": field, "left": a, "right": b,
                            "status": "unknown", "relation": "format query unavailable"})
        else:
            results.append({
                "capability": field, "left": a, "right": b,
                "status": "same" if a == b else "different_masks",
                "left_only_bits": a & ~b, "right_only_bits": b & ~a,
                "relation": "raw SDK bitmasks; usage flags are not decoded here",
            })

    return {
        "schema_version": GPU_PROBE_SCHEMA_VERSION,
        "comparison": "windows_d3d12_adapter_capabilities",
        "left_adapter": left.get("name", "unnamed"),
        "right_adapter": right.get("name", "unnamed"),
        "capability_count": len(results),
        "summary": {
            "same": sum(item["status"] == "same" for item in results),
            "left_higher": sum(item["status"] == "left_higher" for item in results),
            "right_higher": sum(item["status"] == "right_higher" for item in results),
            "left_only": sum(item["status"] == "left_only" for item in results),
            "right_only": sum(item["status"] == "right_only" for item in results),
            "different_masks": sum(item["status"] == "different_masks" for item in results),
            "unknown": sum(item["status"] == "unknown" for item in results),
        },
        "results": results,
        "limitations": [
            "Compares reported Windows D3D12 adapter capabilities only.",
            "Does not measure performance or current memory budget.",
            "Raw format support masks are not decoded into specific usage claims.",
            "Does not establish Xbox D3D12.x support or game compatibility.",
        ],
    }
