import pytest

from orion_core.pipeline_state import PipelineDescription, assess_pipeline


def test_valid_graphics_pipeline_needs_hardware_validation():
    desc = PipelineDescription("basic", "triangle", ("vertex", "pixel"),
                               ("R8G8B8A8_UNORM",), input_layout=True)
    result = assess_pipeline(desc)
    assert result["status"] == "hardware_validation_needed"
    assert result["native_pso_creation_performed"] is False


def test_compute_pipeline_rejects_graphics_combination():
    desc = PipelineDescription("bad", "triangle", ("compute", "pixel"))
    assert "compute stage cannot be combined with graphics stages" in desc.validate()


def test_mesh_pipeline_rejects_vertex_and_amplification_without_mesh():
    assert PipelineDescription("bad", "triangle", ("mesh", "vertex")).validate()
    assert PipelineDescription("bad", "triangle", ("amplification",)).validate()


def test_sample_count_and_depth_state_are_validated():
    desc = PipelineDescription("bad", "triangle", ("vertex", "pixel"),
                               sample_count=3, depth_test_enabled=True)
    errors = desc.validate()
    assert "sample_count must be a positive power of two" in errors
    assert "depth testing requires a depth format" in errors


def test_invalid_description_status():
    desc = PipelineDescription("", "banana", ())
    assert assess_pipeline(desc)["status"] == "invalid_description"
