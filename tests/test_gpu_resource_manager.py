import pytest

from orion_core.gpu_resource_manager import GPUResourceManager
from orion_core.graphics_harness import ResourceState
from orion_core.resource_streaming import ResourcePriority, ResourceStatus


def _resident(manager, resource_id="texture", size=64):
    manager.request(resource_id, size)
    point = manager.submit_next_upload()
    assert point is not None
    with pytest.raises(RuntimeError):
        manager.submit_use(resource_id, "graphics")
    manager.complete_copy(point.value)
    return point


def test_full_lifecycle_waits_for_all_queue_users_and_releases_budget():
    manager = GPUResourceManager(256)
    _resident(manager)
    manager.transition("texture", ResourceState.SHADER_RESOURCE)
    graphics = manager.submit_use("texture", "graphics")
    compute = manager.submit_use("texture", "compute")
    assert manager.snapshot()["used_bytes"] == 64

    manager.retire("texture")
    with pytest.raises(RuntimeError):
        manager.submit_use("texture", "graphics")
    manager.complete_queue("graphics", graphics.value)
    assert manager.collect() == []
    assert manager.snapshot()["used_bytes"] == 64
    manager.complete_queue("compute", compute.value)
    assert manager.collect() == ["texture"]
    assert manager.snapshot()["used_bytes"] == 0


def test_retirement_of_upload_pending_resource_waits_for_copy_fence():
    manager = GPUResourceManager(128)
    manager.request("pending", 32)
    copy = manager.submit_next_upload()
    manager.retire("pending")
    assert manager.collect() == []
    manager.complete_copy(copy.value)
    assert manager.collect() == ["pending"]
    assert manager.snapshot()["used_bytes"] == 0


def test_transition_rejected_before_upload_completion():
    manager = GPUResourceManager(128)
    manager.request("x", 16)
    manager.submit_next_upload()
    with pytest.raises(RuntimeError):
        manager.transition("x", ResourceState.SHADER_RESOURCE)


def test_retirement_requires_submitted_work_and_unknown_queue_is_rejected():
    manager = GPUResourceManager(128)
    manager.request("x", 16)
    with pytest.raises(ValueError):
        manager.retire("x")
    with pytest.raises(KeyError):
        manager.submit_use("x", "video")


def test_snapshot_exposes_simulation_boundary():
    manager = GPUResourceManager(64)
    data = manager.snapshot()
    assert data["simulation_only"] is True
    assert data["gpu_commands_executed"] is False
    assert data["gpu_resources_created_or_destroyed"] is False



def test_manager_integrates_explicit_cross_queue_waits():
    manager = GPUResourceManager(256)
    _resident(manager)
    graphics = manager.submit_use("texture", "graphics")
    compute = manager.submit_use("texture", "compute", wait_for=("graphics",))
    with pytest.raises(RuntimeError, match="waiting for producer"):
        manager.complete_queue("compute", compute.value)
    manager.complete_queue("graphics", graphics.value)
    manager.complete_queue("compute", compute.value)
    snapshot = manager.snapshot()
    assert snapshot["queue_synchronization"]["gpu_queue_waits_issued"] is False


def test_manager_rejects_wait_for_queue_without_resource_use():
    manager = GPUResourceManager(128)
    _resident(manager)
    with pytest.raises(ValueError, match="no submitted use"):
        manager.submit_use("texture", "compute", wait_for=("graphics",))
