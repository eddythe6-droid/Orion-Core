import pytest

from orion_core.resource_streaming import ResourcePriority, ResourceStatus
from orion_core.streaming_gpu import FenceAwareStreamingEngine


def test_upload_is_not_usable_until_copy_fence_completes():
    engine = FenceAwareStreamingEngine(100)
    engine.request('texture', 60, ResourcePriority.HIGH)
    pending = engine.submit_next_upload()
    assert pending is not None
    assert engine.streaming.resources['texture'].status == ResourceStatus.UPLOAD_PENDING
    with pytest.raises(RuntimeError, match='still in flight'):
        engine.touch('texture')
    assert engine.complete_uploads(pending.fence.value) == ['texture']
    assert engine.streaming.resources['texture'].status == ResourceStatus.RESIDENT
    engine.touch('texture')


def test_pending_upload_allocation_is_not_evicted_before_fence():
    engine = FenceAwareStreamingEngine(100)
    engine.request('texture', 60, ResourcePriority.LOW)
    pending = engine.submit_next_upload()
    engine.request('urgent', 60, ResourcePriority.CRITICAL)
    failed = engine.streaming.process_next()
    assert failed.status == ResourceStatus.FAILED
    assert engine.streaming.resources['texture'].status == ResourceStatus.UPLOAD_PENDING
    engine.complete_uploads(pending.fence.value)
    assert engine.streaming.resources['texture'].status == ResourceStatus.RESIDENT


def test_fence_completion_is_monotonic_and_cannot_exceed_submitted():
    engine = FenceAwareStreamingEngine(100)
    engine.request('a', 10)
    pending = engine.submit_next_upload()
    with pytest.raises(ValueError):
        engine.complete_uploads(pending.fence.value + 1)
    assert engine.complete_uploads(pending.fence.value) == ['a']


def test_snapshot_discloses_simulation_limits():
    engine = FenceAwareStreamingEngine(128)
    snapshot = engine.snapshot()
    assert snapshot['simulation_only'] is True
    assert snapshot['gpu_commands_executed'] is False
