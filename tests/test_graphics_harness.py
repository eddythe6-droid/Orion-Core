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


def test_resource_state_tracker_validates_and_records_transitions():
    from orion_core.graphics_harness import ResourceState, ResourceStateTracker

    tracker = ResourceStateTracker()
    tracker.register("texture", ResourceState.COPY_DEST)
    first = tracker.transition(
        "texture", ResourceState.COPY_DEST, ResourceState.SHADER_RESOURCE
    )
    second = tracker.transition(
        "texture", ResourceState.SHADER_RESOURCE, ResourceState.RENDER_TARGET
    )

    assert tracker.state_of("texture") == ResourceState.RENDER_TARGET
    assert tracker.history == (first, second)
    assert first.resource_id == "texture"
    assert first.before == ResourceState.COPY_DEST
    assert first.after == ResourceState.SHADER_RESOURCE


def test_resource_state_tracker_rejects_wrong_before_state_and_noop():
    from orion_core.graphics_harness import ResourceState, ResourceStateTracker

    tracker = ResourceStateTracker()
    tracker.register("buffer", ResourceState.COMMON)
    with pytest.raises(ValueError, match="before-state mismatch"):
        tracker.transition("buffer", ResourceState.COPY_DEST, ResourceState.COPY_SOURCE)
    with pytest.raises(ValueError, match="no-op"):
        tracker.transition("buffer", ResourceState.COMMON, ResourceState.COMMON)
    assert tracker.state_of("buffer") == ResourceState.COMMON
    assert tracker.history == ()


def test_resource_state_tracker_rejects_unknown_and_duplicate_resources():
    from orion_core.graphics_harness import ResourceState, ResourceStateTracker

    tracker = ResourceStateTracker()
    with pytest.raises(KeyError, match="unknown resource"):
        tracker.state_of("missing")
    with pytest.raises(ValueError, match="unique"):
        tracker.register("", ResourceState.COMMON)
    tracker.register("buffer", ResourceState.COMMON)
    with pytest.raises(ValueError, match="unique"):
        tracker.register("buffer", ResourceState.COPY_DEST)
