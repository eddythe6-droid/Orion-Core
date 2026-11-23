"""Declarative D3D12 root-signature layout validation (not native serialization)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

VISIBILITIES = {"all", "vertex", "pixel", "geometry", "hull", "domain", "compute", "mesh", "amplification"}
RANGE_TYPES = {"srv", "uav", "cbv", "sampler"}
PARAMETER_TYPES = {"descriptor_table", "root_constants", "root_cbv", "root_srv", "root_uav"}


@dataclass(frozen=True)
class DescriptorRange:
    range_type: str
    count: int
    base_register: int = 0
    register_space: int = 0


@dataclass(frozen=True)
class RootParameter:
    parameter_type: str
    visibility: str = "all"
    ranges: tuple[DescriptorRange, ...] = ()
    num_32bit_values: int = 0
    shader_register: int = 0
    register_space: int = 0


@dataclass(frozen=True)
class RootSignatureDescription:
    parameters: tuple[RootParameter, ...]
    static_sampler_count: int = 0
    allow_input_assembler: bool = True

    def validate(self) -> list[str]:
        errors: list[str] = []
        if len(self.parameters) > 64:
            errors.append("root signature cannot contain more than 64 parameters")
        if self.static_sampler_count < 0:
            errors.append("static_sampler_count cannot be negative")
        cost = 0
        for index, param in enumerate(self.parameters):
            prefix = f"parameter {index}: "
            if param.parameter_type not in PARAMETER_TYPES:
                errors.append(prefix + "unknown parameter type")
                continue
            if param.visibility not in VISIBILITIES:
                errors.append(prefix + "unknown shader visibility")
            if param.parameter_type == "descriptor_table":
                cost += 1
                if not param.ranges:
                    errors.append(prefix + "descriptor table must contain at least one range")
                for item in param.ranges:
                    if item.range_type not in RANGE_TYPES:
                        errors.append(prefix + "unknown descriptor range type")
                    if item.count <= 0:
                        errors.append(prefix + "descriptor range count must be positive")
                    if item.base_register < 0 or item.register_space < 0:
                        errors.append(prefix + "register and register space must be non-negative")
                if param.num_32bit_values:
                    errors.append(prefix + "descriptor table cannot declare root constants")
            elif param.parameter_type == "root_constants":
                cost += param.num_32bit_values
                if param.num_32bit_values <= 0:
                    errors.append(prefix + "root constants must contain at least one 32-bit value")
                if param.ranges:
                    errors.append(prefix + "root constants cannot contain descriptor ranges")
            else:
                cost += 2
                if param.ranges or param.num_32bit_values:
                    errors.append(prefix + "root descriptor cannot contain ranges or root constants")
                if param.shader_register < 0 or param.register_space < 0:
                    errors.append(prefix + "register and register space must be non-negative")
        if cost > 64:
            errors.append("root signature cost exceeds the 64-DWORD limit")
        return errors

    def root_cost_dwords(self) -> int:
        return sum(1 if p.parameter_type == "descriptor_table" else
                   p.num_32bit_values if p.parameter_type == "root_constants" else 2
                   for p in self.parameters)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_root_signature(description: RootSignatureDescription) -> dict[str, Any]:
    errors = description.validate()
    return {
        "schema_version": 1,
        "status": "invalid_description" if errors else "native_validation_needed",
        "root_cost_dwords": description.root_cost_dwords(),
        "validation_errors": errors,
        "native_serialization_performed": False,
        "root_signature_created": False,
        "description": description.to_dict(),
        "limitations": [
            "This is structural bookkeeping, not D3D12 root-signature serialization.",
            "Register overlap, static sampler definitions, versioned flags, and driver validation are not fully modeled.",
            "No descriptor heap or command-list binding is performed.",
        ],
    }
