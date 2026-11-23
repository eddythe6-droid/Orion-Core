import pytest

from orion_core.descriptor_heap import DescriptorHeapManager
from orion_core.gpu_lifetime import QueueSet
from orion_core.graphics_harness import FencePoint


def test_descriptor_range_waits_for_every_queue_before_reuse():
    queues = QueueSet()
    graphics = queues.add("graphics")
    compute = queues.add("compute")
    heap = DescriptorHeapManager(4, queues)
    first = heap.allocate("texture", 3)
    g = graphics.submit()
    c = compute.submit()
    heap.retire("texture", (g, c))
    assert heap.collect() == []
    with pytest.raises(MemoryError):
        heap.allocate("other", 2)
    graphics.complete(g.value)
    assert heap.collect() == []
    compute.complete(c.value)
    assert heap.collect() == [first]
    assert heap.allocate("other", 3) == first


def test_descriptor_heap_rejects_invalid_retirement_and_duplicate_ids():
    queues = QueueSet()
    queues.add("copy")
    heap = DescriptorHeapManager(2, queues)
    heap.allocate("a", 1)
    with pytest.raises(ValueError):
        heap.allocate("a", 1)
    with pytest.raises(ValueError):
        heap.retire("a", ())
    with pytest.raises(ValueError):
        heap.retire("a", (FencePoint("copy", 1),))


def test_descriptor_heap_validates_capacity_and_count():
    queues = QueueSet()
    heap = DescriptorHeapManager(2, queues)
    with pytest.raises(ValueError):
        DescriptorHeapManager(0, queues)
    with pytest.raises(ValueError):
        heap.allocate("bad", 0)
    heap.allocate("a", 2)
    with pytest.raises(MemoryError):
        heap.allocate("b", 1)


def test_descriptor_heap_snapshot_marks_simulation_boundary():
    queues = QueueSet()
    heap = DescriptorHeapManager(8, queues)
    state = heap.snapshot()
    assert state["simulation_only"] is True
    assert state["native_descriptor_heap_created"] is False
