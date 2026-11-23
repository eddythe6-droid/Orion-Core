import json

import pytest

from orion_core.gpu_probe import (
    ProbeReportError,
    summarize_probe_report,
    validate_probe_report,
    compare_gpu_adapters,
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



def test_compare_gpu_adapters_orders_known_tiers_and_preserves_unknowns():
    left = {
        "name": "GPU A", "feature_level": "12_1", "shader_model": "6_6",
        "resource_binding_tier": "3", "raytracing_tier": "1_1",
        "mesh_shader_tier": "unknown", "sampler_feedback_tier": "not_supported",
        "wave_ops": True, "int64_shader_ops": True,
        "expanded_compute_resource_states": False,
        "rgba8_support1": 15, "rgba8_support2": 0,
    }
    right = {
        "name": "GPU B", "feature_level": "12_0", "shader_model": "6_6",
        "resource_binding_tier": "2", "raytracing_tier": "not_supported",
        "mesh_shader_tier": "1", "sampler_feedback_tier": "not_supported",
        "wave_ops": False, "int64_shader_ops": True,
        "expanded_compute_resource_states": False,
        "rgba8_support1": 7, "rgba8_support2": 0,
    }
    report = compare_gpu_adapters(left, right)
    by_name = {item["capability"]: item for item in report["results"]}
    assert by_name["feature_level"]["status"] == "left_higher"
    assert by_name["resource_binding_tier"]["status"] == "left_higher"
    assert by_name["raytracing_tier"]["status"] == "left_higher"
    assert by_name["mesh_shader_tier"]["status"] == "unknown"
    assert by_name["wave_ops"]["status"] == "left_only"
    assert by_name["rgba8_support1"]["left_only_bits"] == 8
    assert report["summary"]["unknown"] == 1


def test_compare_gpu_adapters_does_not_guess_missing_boolean_support():
    report = compare_gpu_adapters({"name": "A"}, {"name": "B"})
    wave = next(item for item in report["results"] if item["capability"] == "wave_ops")
    assert wave["status"] == "unknown"



def test_format_query_records_are_validated_and_preserved():
    report = sample_report()
    report["adapters"][0]["formats"] = [{
        "format": "BC7_UNORM", "query_available": True,
        "support1": 123, "support2": 0,
    }]
    summary = summarize_probe_report(report)
    assert summary["adapters"][0]["formats"][0]["format"] == "BC7_UNORM"

    report["adapters"][0]["formats"][0]["support1"] = -1
    with pytest.raises(ProbeReportError, match="support1"):
        validate_probe_report(report)


def test_unavailable_format_query_keeps_null_masks():
    report = sample_report()
    report["adapters"][0]["formats"] = [{
        "format": "BC7_UNORM", "query_available": False,
        "support1": None, "support2": None,
    }]
    assert validate_probe_report(report)["adapters"][0]["formats"][0]["support1"] is None



def test_resource_copy_smoke_fields_are_validated_and_summarized():
    report = sample_report()
    adapter = report["adapters"][0]
    adapter["resource_copy_smoke_test"] = True
    adapter["resource_copy_smoke_note"] = "upload_copy_barrier_readback_verified"
    summary = summarize_probe_report(report)
    assert summary["adapters"][0]["resource_copy_smoke_test"] is True
    assert summary["adapters"][0]["resource_copy_smoke_note"] == "upload_copy_barrier_readback_verified"

    adapter["resource_copy_smoke_test"] = "true"
    with pytest.raises(ProbeReportError, match="resource_copy_smoke_test"):
        validate_probe_report(report)

    adapter["resource_copy_smoke_test"] = False
    adapter["resource_copy_smoke_note"] = None
    with pytest.raises(ProbeReportError, match="resource_copy_smoke_note"):
        validate_probe_report(report)



def test_binding_smoke_fields_are_validated_and_summarized():
    report = sample_report()
    adapter = report["adapters"][0]
    adapter.update({
        "root_signature_smoke_test": True,
        "resource_descriptor_heap_smoke_test": True,
        "sampler_descriptor_heap_smoke_test": False,
        "resource_descriptor_increment": 32,
        "sampler_descriptor_increment": 16,
        "binding_smoke_note": "root_signature_and_heaps_created",
    })
    summary = summarize_probe_report(report)["adapters"][0]
    assert summary["root_signature_smoke_test"] is True
    assert summary["resource_descriptor_heap_smoke_test"] is True
    assert summary["sampler_descriptor_heap_smoke_test"] is False
    assert summary["resource_descriptor_increment"] == 32
    assert summary["sampler_descriptor_increment"] == 16
    assert summary["binding_smoke_note"] == "root_signature_and_heaps_created"

    adapter["resource_descriptor_increment"] = -1
    with pytest.raises(ProbeReportError, match="resource_descriptor_increment"):
        validate_probe_report(report)

    adapter["resource_descriptor_increment"] = 32
    adapter["root_signature_smoke_test"] = "true"
    with pytest.raises(ProbeReportError, match="root_signature_smoke_test"):
        validate_probe_report(report)
