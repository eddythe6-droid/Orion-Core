from orion_core.resource_binding import assess_binding_requirements


def test_binding_tier_meets_requirement():
    result = assess_binding_requirements("tier_2", {"name": "GPU", "resource_binding_tier": "tier_3"})
    assert result["status"] == "satisfied"


def test_binding_tier_below_requirement():
    result = assess_binding_requirements("tier_3", {"resource_binding_tier": "tier_1"})
    assert result["status"] == "not_satisfied"


def test_missing_binding_tier_is_unknown():
    assert assess_binding_requirements("tier_2", {})["status"] == "unknown"
