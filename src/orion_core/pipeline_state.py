"""Declarative graphics pipeline descriptions and conservative validation.

This module validates input consistency only. It does not create native D3D12 PSOs
or claim that a driver accepts a pipeline.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

SHADER_STAGES = {"vertex", "pixel", "geometry", "hull", "domain", "compute", "mesh", "amplification"}
TOPOLOGIES = {"point", "line", "triangle", "patch", "unknown"}


@dataclass(frozen=True)
class PipelineDescription:
    name: str
    topology: str
    shader_stages: tuple[str, ...]
    render_target_formats: tuple[str, ...] = ()
    depth_format: str | None = None
    sample_count: int = 1
    input_layout: bool = True
    blend_enabled: bool = False
    depth_test_enabled: bool = False

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("name must not be empty")
        if self.topology not in TOPOLOGIES:
            errors.append("topology is not recognized")
        if not self.shader_stages:
            errors.append("at least one shader stage is required")
        if len(set(self.shader_stages)) != len(self.shader_stages):
            errors.append("shader stages must be unique")
        if any(stage not in SHADER_STAGES for stage in self.shader_stages):
            errors.append("one or more shader stages are not recognized")
        if self.sample_count < 1 or self.sample_count & (self.sample_count - 1):
            errors.append("sample_count must be a positive power of two")
        if len(self.render_target_formats) > 8:
            errors.append("at most eight render targets are allowed")
        if "compute" in self.shader_stages and len(self.shader_stages) != 1:
            errors.append("compute stage cannot be combined with graphics stages")
        if "mesh" in self.shader_stages and "vertex" in self.shader_stages:
            errors.append("mesh and vertex stages cannot be combined")
        if "amplification" in self.shader_stages and "mesh" not in self.shader_stages:
            errors.append("amplification stage requires mesh stage")
        if "vertex" not in self.shader_stages and "mesh" not in self.shader_stages and "compute" not in self.shader_stages:
            errors.append("graphics pipeline requires vertex or mesh stage")
        if self.input_layout and "vertex" not in self.shader_stages:
            errors.append("input layout is only meaningful with a vertex stage")
        if self.depth_test_enabled and not self.depth_format:
            errors.append("depth testing requires a depth format")
        return errors

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["shader_stages"] = list(self.shader_stages)
        data["render_target_formats"] = list(self.render_target_formats)
        return data


def assess_pipeline(description: PipelineDescription, adapter: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return structural validation and explicit hardware-validation status."""
    errors = description.validate()
    result: dict[str, Any] = {
        "pipeline": description.to_dict(),
        "status": "invalid_description" if errors else "hardware_validation_needed",
        "validation_errors": errors,
        "native_pso_creation_performed": False,
        "driver_acceptance_established": False,
    }
    if adapter is not None:
        result["adapter_name"] = adapter.get("name", "unknown")
        result["adapter_capabilities_consulted"] = False
        result["note"] = "Adapter data is not sufficient to prove PSO creation; shader bytecode and full PSO state are not tested."
    else:
        result["adapter_name"] = None
        result["note"] = "No adapter report supplied; native D3D12 PSO creation is required for hardware validation."
    return result
