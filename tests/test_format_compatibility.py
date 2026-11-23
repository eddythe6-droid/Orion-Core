from orion_core.format_compatibility import assess_format_requirements, compare_format_reports


def test_format_query_does_not_overclaim_usage_support():
    adapter = {"name": "GPU", "formats": [{"format": "R8G8B8A8_UNORM",
        "query_available": True, "support1": 123, "support2": 0}]}
    result = assess_format_requirements(["R8G8B8A8_UNORM"], adapter)
    assert result["overall"] == "hardware_validation_needed"
    assert result["results"][0]["support1"] == 123


def test_missing_format_is_unknown():
    result = assess_format_requirements(["BC7_UNORM"], {"formats": []})
    assert result["overall"] == "unknown"


def test_compare_raw_masks_only():
    a = {"formats": [{"format": "X", "query_available": True, "support1": 3, "support2": 1}]}
    b = {"formats": [{"format": "X", "query_available": True, "support1": 1, "support2": 1}]}
    assert compare_format_reports(a, b)["formats"][0]["status"] == "different_raw_masks"
