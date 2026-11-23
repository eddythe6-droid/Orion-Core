import pytest

from orion_core.gpu_lifetime import QueueSet
from orion_core.queue_sync import QueueSynchronizer


def test_consumer_completion_waits_for_producer_fence():
    queues = QueueSet()
    copy = queues.add("copy")
    graphics = queues.add("graphics")
    producer = copy.submit()
    sync = QueueSynchronizer(queues)
    sync.wait("graphics", producer)
    consumer = sync.submit("graphics")

    with pytest.raises(RuntimeError, match="waiting for producer"):
        sync.complete("graphics", consumer.value)
    sync.complete("copy", producer.value)
    sync.complete("graphics", consumer.value)
    assert queues.is_complete(consumer)


def test_wait_rejects_unknown_and_unsubmitted_producer_fences():
    queues = QueueSet()
    queues.add("graphics")
    sync = QueueSynchronizer(queues)
    from orion_core.graphics_harness import FencePoint
    with pytest.raises(KeyError):
        sync.wait("graphics", FencePoint("missing", 1))
    queues.add("copy")
    with pytest.raises(ValueError, match="already submitted"):
        sync.wait("graphics", FencePoint("copy", 1))


def test_wait_rejects_self_dependency_and_detects_cycles():
    queues = QueueSet()
    copy = queues.add("copy")
    graphics = queues.add("graphics")
    compute = queues.add("compute")
    sync = QueueSynchronizer(queues)
    c = copy.submit()
    g = graphics.submit()
    k = compute.submit()

    with pytest.raises(ValueError, match="own fence"):
        sync.wait("copy", c)
    sync.wait("graphics", c)
    sync.wait("compute", g)
    with pytest.raises(ValueError, match="cycle"):
        sync.wait("copy", k)


def test_completed_producer_needs_no_queued_wait():
    queues = QueueSet()
    copy = queues.add("copy")
    queues.add("graphics")
    producer = copy.submit()
    queues.complete("copy", producer.value)
    sync = QueueSynchronizer(queues)
    sync.wait("graphics", producer)
    assert sync.snapshot()["pending_waits"] == {}
    assert sync.can_submit_use("graphics", producer)


def test_snapshot_is_explicitly_simulated():
    queues = QueueSet()
    queues.add("copy")
    queues.add("graphics")
    snapshot = QueueSynchronizer(queues).snapshot()
    assert snapshot["simulation_only"] is True
    assert snapshot["gpu_queue_waits_issued"] is False
