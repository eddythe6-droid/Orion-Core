from orion_core.shader_compatibility import assess_shader_requirements


def test_known_boolean_and_tier_requirements():
    adapter = {"name": "GPU", "wave_ops": True, "raytracing_tier": "1_1"}
    result = assess_shader_requirements({"wave_ops": True, "raytracing": "1_0"}, adapter)
    assert result["overall"] == "satisfied"
    assert all(item["status"] == "satisfied" for item in result["results"])


def test_missing_capability_remains_unknown():
    result = assess_shader_requirements({"mesh_shaders": "1_0"}, {"name": "GPU"})
    assert result["overall"] == "unknown"
    assert result["results"][0]["status"] == "unknown"


def test_known_missing_feature_is_not_satisfied():
    result = assess_shader_requirements({"int64_shader_ops": True}, {"int64_shader_ops": False})
    assert result["overall"] == "not_satisfied"


def test_unknown_feature_is_preserved_as_unknown():
    result = assess_shader_requirements({"vendor_magic": True}, {})
    assert result["results"][0]["status"] == "unknown"
