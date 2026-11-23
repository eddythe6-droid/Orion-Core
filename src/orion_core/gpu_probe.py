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
