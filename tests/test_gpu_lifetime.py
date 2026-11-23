import pytest

from orion_core.gpu_lifetime import DeferredReleaseQueue, QueueSet
from orion_core.graphics_harness import FencePoint


def test_resource_waits_for_every_queue_that_used_it():
    queues = QueueSet()
    copy = queues.add('copy')
    graphics = queues.add('graphics')
    compute = queues.add('compute')
    copy_point = copy.submit()
    graphics_point = graphics.submit()
    compute_point = compute.submit()
    retired = DeferredReleaseQueue(queues)
    retired.retire('texture', [copy_point, graphics_point, compute_point])
    queues.complete('copy', copy_point.value)
    queues.complete('graphics', graphics_point.value)
    assert retired.collect() == []
    assert len(retired.pending) == 1
    queues.complete('compute', compute_point.value)
    assert retired.collect() == ['texture']
    assert retired.collect() == []


def test_retirement_rejects_unknown_or_unsubmitted_fence():
    queues = QueueSet()
    queues.add('copy')
    retired = DeferredReleaseQueue(queues)
    with pytest.raises(ValueError):
        retired.retire('x', [])
    with pytest.raises(ValueError):
        retired.retire('x', [FencePoint('copy', 1)])


def test_queue_names_are_unique_and_unknown_names_rejected():
    queues = QueueSet()
    queues.add('copy')
    with pytest.raises(ValueError):
        queues.add('copy')
    with pytest.raises(KeyError):
        queues.submit('unknown')


def test_snapshot_states_simulation_boundary():
    queues = QueueSet()
    queues.add('graphics')
    snapshot = DeferredReleaseQueue(queues).snapshot()
    assert snapshot['simulation_only'] is True
    assert snapshot['gpu_resources_destroyed'] is False
