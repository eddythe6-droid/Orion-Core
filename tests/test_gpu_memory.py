import pytest

from orion_core.gpu_memory import (
    MemoryPressure,
    SimulatedMemoryPool,
    analyze_memory_pool,
    analyze_probe_memory,
)


def test_memory_pressure_thresholds_and_available_capacity():
    low = analyze_memory_pool("local", 1000, 500)
    moderate = analyze_memory_pool("local", 1000, 750)
    high = analyze_memory_pool("local", 1000, 950)
    over = analyze_memory_pool("local", 1000, 1100)
    assert low.pressure == MemoryPressure.LOW
    assert moderate.pressure == MemoryPressure.MODERATE
    assert high.pressure == MemoryPressure.HIGH
    assert over.pressure == MemoryPressure.OVER_BUDGET
    assert over.available_bytes == 0


def test_unknown_or_zero_budget_is_not_assumed_to_be_empty():
    assert analyze_memory_pool("local", None, 0).pressure == MemoryPressure.UNKNOWN
    assert analyze_memory_pool("local", 0, 0).utilization is None


def test_reject_invalid_memory_values():
    with pytest.raises(ValueError):
        analyze_memory_pool("local", -1, 0)
    with pytest.raises(ValueError):
        analyze_memory_pool("local", 100, True)


def test_simulated_pool_allocation_release_and_exhaustion():
    pool = SimulatedMemoryPool(100)
    pool.allocate("texture", 70)
    assert pool.used_bytes == 70
    with pytest.raises(MemoryError, match="exhausted"):
        pool.allocate("buffer", 40)
    assert pool.release("texture") == 70
    pool.allocate("buffer", 40)
    assert pool.available_bytes == 60


def test_probe_memory_summary_keeps_missing_pools_unknown():
    result = analyze_probe_memory({"name": "GPU"})
    assert result["pools"]["local"]["pressure"] == "unknown"
    assert result["pools"]["non_local"]["pressure"] == "unknown"
    assert result["game_compatibility_established"] is False


def test_probe_memory_summary_uses_dxgi_budget_and_usage_fields():
    from orion_core.gpu_probe import summarize_gpu_memory
    report = {
        "schema_version": 1, "probe": "orion_d3d12_probe", "available": True,
        "adapters": [{
            "name": "GPU", "software": False, "d3d12_device": True,
            "video_memory": {
                "local": {"query_available": True, "budget_bytes": 1000, "current_usage_bytes": 950, "available_for_reservation_bytes": 50},
                "non_local": {"query_available": False, "budget_bytes": None, "current_usage_bytes": None, "available_for_reservation_bytes": None},
            },
        }],
    }
    result = summarize_gpu_memory(report)
    assert result["adapters"][0]["pools"]["local"]["pressure"] == "high"
    assert result["adapters"][0]["pools"]["non_local"]["pressure"] == "unknown"
