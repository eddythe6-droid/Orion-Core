"""Unified, conservative graphics compatibility research report."""
from __future__ import annotations

from typing import Any

from .format_compatibility import assess_format_requirements
from .pipeline_state import PipelineDescription, assess_pipeline
from .resource_binding import assess_binding_requirements
from .root_signature import RootSignatureDescription, assess_root_signature
from .shader_compatibility import assess_shader_requirements


def build_graphics_compatibility_report(
    adapter: dict[str, Any],
    pipeline: PipelineDescription,
    shader_requirements: dict[str, Any] | None = None,
    required_formats: list[str] | None = None,
    required_binding_tier: str | None = None,
    root_signature: RootSignatureDescription | None = None,
) -> dict[str, Any]:
    """Combine research checks; never promote incomplete evidence to compatible."""
    sections = {
        "pipeline": assess_pipeline(pipeline, adapter),
        "shaders": assess_shader_requirements(shader_requirements or {}, adapter),
        "formats": assess_format_requirements(required_formats or [], adapter),
        "resource_binding": assess_binding_requirements(required_binding_tier, adapter) if required_binding_tier is not None else {\n            "status": "not_provided", "reason": "no binding tier requirement was declared",\n        },
        "root_signature": assess_root_signature(root_signature) if root_signature is not None else {
            "status": "not_provided", "native_serialization_performed": False,
            "root_signature_created": False,
        },
    }
    statuses = []
    statuses.append(sections["pipeline"]["status"])
    statuses.append(sections["shaders"]["overall"])
    statuses.append(sections["formats"]["overall"])
    if sections["resource_binding"]["status"] != "not_provided":\n        statuses.append(sections["resource_binding"]["status"])
    if sections["root_signature"]["status"] not in {"not_provided", "native_validation_needed"}:
        statuses.append(sections["root_signature"]["status"])
    if "invalid_description" in statuses or "not_satisfied" in statuses:
        overall = "requirements_not_met"
    elif "unknown" in statuses:
        overall = "incomplete_evidence"
    else:
        overall = "hardware_validation_needed"
    return {
        "schema_version": 1,
        "report": "orion_graphics_compatibility",
        "adapter": adapter.get("name", "unknown"),
        "overall": overall,
        "sections": sections,
        "interpretation": {
            "native_pso_created": False,
            "shader_bytecode_compiled": False,
            "gpu_workload_executed": False,
            "xbox_compatibility_established": False,
            "game_compatibility_established": False,
        },
        "limitations": [
            "This report combines declared requirements and probe metadata only.",
            "A hardware validation run is required before asserting native pipeline compatibility.",
            "Xbox D3D12.x behavior is not emulated by this Windows D3D12 assessment.",
        ],
    }
