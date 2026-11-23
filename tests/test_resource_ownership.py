import pytest

from orion_core.graphics_harness import FencePoint
from orion_core.resource_ownership import ResourceOwnershipTracker


def test_resource_ownership_records_cross_queue_handoffs():
    tracker = ResourceOwnershipTracker()
    tracker.register("texture")
    assert tracker.owner_of("texture") is None
    first = tracker.transfer("texture", "copy", None)
    second = tracker.transfer("texture", "graphics", FencePoint("copy", 4))
    assert first.previous_queue is None
    assert second.previous_queue == "copy"
    assert tracker.owner_of("texture") == "graphics"


def test_ownership_transfer_requires_valid_dependency():
    tracker = ResourceOwnershipTracker()
    tracker.register("buffer")
    tracker.transfer("buffer", "compute", None)
    with pytest.raises(ValueError, match="requires a dependency"):
        tracker.transfer("buffer", "graphics", None)
    with pytest.raises(ValueError, match="previous owner"):
        tracker.transfer("buffer", "graphics", FencePoint("copy", 1))


def test_ownership_rejects_duplicate_or_unknown_resources():
    tracker = ResourceOwnershipTracker()
    with pytest.raises(ValueError):
        tracker.register("")
    tracker.register("x")
    with pytest.raises(ValueError):
        tracker.register("x")
    with pytest.raises(KeyError):
        tracker.owner_of("missing")


def test_ownership_snapshot_marks_simulation_only():
    tracker = ResourceOwnershipTracker()
    tracker.register("x")
    snapshot = tracker.snapshot()
    assert snapshot["simulation_only"] is True
    assert snapshot["gpu_ownership_transfers_executed"] is False
