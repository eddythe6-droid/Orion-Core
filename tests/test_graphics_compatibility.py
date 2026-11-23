from orion_core.graphics_compatibility import build_graphics_compatibility_report
from orion_core.pipeline_state import PipelineDescription


def test_unified_report_stays_hardware_validation_needed():
    adapter = {"name": "GPU", "resource_binding_tier": "tier_2",
        "wave_ops": True, "formats": [{"format": "R8G8B8A8_UNORM",
        "query_available": True, "support1": 1, "support2": 0}]}
    pipeline = PipelineDescription("basic", "triangle", ("vertex", "pixel"),
                                   ("R8G8B8A8_UNORM",))
    report = build_graphics_compatibility_report(
        adapter, pipeline, {"wave_ops": True}, ["R8G8B8A8_UNORM"], "tier_1")
    assert report["overall"] == "hardware_validation_needed"
    assert report["interpretation"]["native_pso_created"] is False


def test_unknown_requirement_prevents_compatibility_claim():
    pipeline = PipelineDescription("basic", "triangle", ("vertex", "pixel"))
    report = build_graphics_compatibility_report({}, pipeline, {"mesh_shaders": "1_0"})
    assert report["overall"] == "incomplete_evidence"


def test_invalid_pipeline_is_not_hidden_by_other_sections():
    pipeline = PipelineDescription("", "invalid", ())
    report = build_graphics_compatibility_report({}, pipeline)
    assert report["overall"] == "requirements_not_met"
