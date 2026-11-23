import pytest

from orion_core.graphics_harness import (
    DescriptorAllocator,
    QueueTimeline,
    ResidencyBudget,
    ResidencyState,
)


def test_queue_fence_must_complete_before_resource_reuse():
    queue = QueueTimeline("direct")
    point = queue.submit()
    with pytest.raises(RuntimeError, match="in flight"):
        queue.require_completed(point)
    queue.complete(point.value)
    queue.require_completed(point)


def test_queue_rejects_foreign_or_invalid_completion():
    queue = QueueTimeline("copy")
    point = queue.submit()
    with pytest.raises(ValueError, match="another queue"):
        queue.has_completed(type(point)("direct", 1))
    with pytest.raises(ValueError, match="monotonic"):
        queue.complete(2)


def test_residency_budget_enforces_capacity_and_evicts():
    budget = ResidencyBudget(100)
    a = budget.add("texture-a", 70)
    budget.add("buffer-b", 40)
    budget.make_resident("texture-a")
    assert a.state == ResidencyState.RESIDENT
    with pytest.raises(MemoryError, match="budget"):
        budget.make_resident("buffer-b")
    budget.evict("texture-a")
    budget.make_resident("buffer-b")
    assert budget.resident_bytes == 40


def test_descriptor_range_is_not_reused_until_fence_completion():
    allocator = DescriptorAllocator(4)
    queue = QueueTimeline("direct")
    first = allocator.allocate(3)
    point = queue.submit()
    allocator.retire(first, point)
    second = allocator.allocate(1)
    assert second.start == 3
    with pytest.raises(MemoryError, match="exhausted"):
        allocator.allocate(1)
    assert allocator.collect([]) == 0
    queue.complete(point.value)
    assert allocator.collect([point]) == 3
    third = allocator.allocate(3)
    assert third == first


def test_descriptor_allocator_rejects_invalid_ranges():
    allocator = DescriptorAllocator(2)
    with pytest.raises(ValueError):
        allocator.allocate(0)
    with pytest.raises(ValueError):
        allocator.retire(type("Range", (), {"start": 0, "count": 1})(),
                         type("Fence", (), {"queue": "q", "value": 1})())
