import json

import pytest

from orion_core.gpu_probe import (
    ProbeReportError,
    summarize_probe_report,
    validate_probe_report,
)


def sample_report():
    return {
        "schema_version": 1,
        "probe": "orion_d3d12_probe",
        "available": True,
        "hardware_d3d12_adapters": 1,
        "adapters": [{
            "name": "Example GPU",
            "software": False,
            "d3d12_device": True,
            "feature_level": "12_1",
            "shader_model": "6_6",
            "resource_binding_tier": "3",
            "raytracing_tier": "not_supported",
            "mesh_shader_tier": "unknown",
            "sampler_feedback_tier": "unknown",
            "direct_queue_fence_test": True,
        }],
    }


def test_validate_native_probe_report():
    report = sample_report()
    assert validate_probe_report(report) == report


def test_rejects_wrong_schema_and_malformed_adapter():
    report = sample_report()
    report["schema_version"] = 99
    with pytest.raises(ProbeReportError, match="schema_version"):
        validate_probe_report(report)

    report = sample_report()
    report["adapters"][0]["software"] = "false"
    with pytest.raises(ProbeReportError, match="software"):
        validate_probe_report(report)


def test_summary_preserves_unknown_and_does_not_claim_game_compatibility():
    summary = summarize_probe_report(sample_report())
    adapter = summary["adapters"][0]
    assert adapter["mesh_shader_tier"] == "unknown"
    assert adapter["sampler_feedback_tier"] == "unknown"
    assert summary["interpretation"]["game_compatibility_established"] is False
    assert summary["interpretation"]["hardware_runtime_validation"] is True


def test_rejects_non_object_report():
    with pytest.raises(ProbeReportError, match="object"):
        validate_probe_report(json.loads("[]"))
