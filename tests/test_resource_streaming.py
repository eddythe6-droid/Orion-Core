import pytest

from orion_core.resource_streaming import (
    ResourcePriority,
    ResourceStatus,
    ResourceStreamingEngine,
)


def test_requests_are_ordered_by_priority_then_fifo():
    engine = ResourceStreamingEngine(100)
    engine.request("normal", 10, ResourcePriority.NORMAL)
    engine.request("critical", 10, ResourcePriority.CRITICAL)
    engine.request("high", 10, ResourcePriority.HIGH)
    assert engine.queue == ["critical", "high", "normal"]
    assert engine.process_next().resource_id == "critical"


def test_higher_priority_request_evicts_oldest_lower_priority_resource():
    engine = ResourceStreamingEngine(100)
    engine.request("old-low", 40, ResourcePriority.LOW)
    engine.process_next()
    engine.request("new-normal", 40, ResourcePriority.NORMAL)
    engine.process_next()
    engine.request("critical", 50, ResourcePriority.CRITICAL)
    result = engine.process_next()
    assert result.status == ResourceStatus.RESIDENT
    assert engine.resources["old-low"].status == ResourceStatus.EVICTED
    assert engine.resources["new-normal"].status == ResourceStatus.RESIDENT
    assert engine.used_bytes == 90


def test_equal_or_higher_priority_and_pinned_resources_are_not_evicted():
    engine = ResourceStreamingEngine(100)
    engine.request("pinned", 40, ResourcePriority.LOW, pinned=True)
    engine.process_next()
    engine.request("same", 40, ResourcePriority.HIGH)
    engine.process_next()
    engine.request("incoming", 50, ResourcePriority.HIGH)
    result = engine.process_next()
    assert result.status == ResourceStatus.FAILED
    assert engine.resources["pinned"].status == ResourceStatus.RESIDENT
    assert engine.resources["same"].status == ResourceStatus.RESIDENT


def test_resource_larger_than_budget_fails_without_accounting_memory():
    engine = ResourceStreamingEngine(32)
    engine.request("huge", 64, ResourcePriority.CRITICAL)
    assert engine.process_next().status == ResourceStatus.FAILED
    assert engine.used_bytes == 0


def test_touch_changes_lru_order_and_release_updates_usage():
    engine = ResourceStreamingEngine(100)
    engine.request("a", 30, ResourcePriority.LOW)
    engine.process_next()
    engine.request("b", 30, ResourcePriority.LOW)
    engine.process_next()
    engine.touch("a")
    engine.request("urgent", 60, ResourcePriority.CRITICAL)
    engine.process_next()
    assert engine.resources["b"].status == ResourceStatus.EVICTED
    assert engine.resources["a"].status == ResourceStatus.RESIDENT
    assert engine.release("urgent") == 60
    assert engine.used_bytes == 30


def test_reject_invalid_capacity_and_duplicate_ids():
    with pytest.raises(ValueError):
        ResourceStreamingEngine(-1)
    engine = ResourceStreamingEngine(10)
    engine.request("x", 1)
    with pytest.raises(ValueError):
        engine.request("x", 1)


def test_snapshot_declares_simulation_limits():
    snapshot = ResourceStreamingEngine(10).snapshot()
    assert snapshot["simulation_only"] is True
    assert snapshot["gpu_upload_performed"] is False
