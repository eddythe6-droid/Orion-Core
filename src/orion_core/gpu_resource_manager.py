"""Integrated GPU resource lifecycle coordinator (deterministic simulation only)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .gpu_lifetime import DeferredReleaseQueue, QueueSet
from .graphics_harness import FencePoint, ResourceState, ResourceStateTracker
from .resource_streaming import ResourcePriority, ResourceStatus
from .streaming_gpu import FenceAwareStreamingEngine


@dataclass(slots=True)
class ManagedResource:
    resource_id: str
    size_bytes: int
    last_use: dict[str, FencePoint] = field(default_factory=dict)
    retired: bool = False


class GPUResourceManager:
    """Compose streaming, queue timelines, state tracking and deferred release.

    This is a CPU-only model. It does not create resources, submit GPU commands,
    execute barriers, or manage actual driver residency.
    """

    QUEUE_NAMES = ("copy", "graphics", "compute")

    def __init__(self, budget_bytes: int) -> None:
        self.streaming = FenceAwareStreamingEngine(budget_bytes, "copy")
        self.queues = QueueSet()
        # The copy timeline is shared with the fence-aware streamer.
        self.queues.queues["copy"] = self.streaming.copy_queue
        self.queues.add("graphics")
        self.queues.add("compute")
        self.states = ResourceStateTracker()
        self.deferred = DeferredReleaseQueue(self.queues)
        self.resources: dict[str, ManagedResource] = {}

    def request(self, resource_id: str, size_bytes: int,
                priority: ResourcePriority = ResourcePriority.NORMAL,
                *, pinned: bool = False) -> ManagedResource:
        if resource_id in self.resources:
            raise ValueError("resource_id must be unique")
        self.streaming.request(resource_id, size_bytes, priority, pinned=pinned)
        managed = ManagedResource(resource_id, size_bytes)
        self.resources[resource_id] = managed
        self.states.register(resource_id, ResourceState.COMMON)
        return managed

    def submit_next_upload(self) -> FencePoint | None:
        pending = self.streaming.submit_next_upload()
        return pending.fence if pending else None

    def complete_copy(self, value: int) -> list[str]:
        return self.streaming.complete_uploads(value)

    def transition(self, resource_id: str, after: ResourceState):
        resource = self._active(resource_id)
        self._require_resident(resource_id)
        before = self.states.state_of(resource_id)
        return self.states.transition(resource_id, before, after)

    def submit_use(self, resource_id: str, queue_name: str) -> FencePoint:
        resource = self._active(resource_id)
        self._require_resident(resource_id)
        if queue_name == "copy":
            raise ValueError("copy work must use submit_next_upload")
        point = self.queues.submit(queue_name)
        resource.last_use[queue_name] = point
        self.streaming.touch(resource_id)
        return point

    def complete_queue(self, queue_name: str, value: int) -> None:
        if queue_name == "copy":
            self.complete_copy(value)
        else:
            self.queues.complete(queue_name, value)

    def retire(self, resource_id: str) -> None:
        resource = self._active(resource_id)
        waits = list(resource.last_use.values())
        if resource_id in self.streaming.pending:
            waits.append(self.streaming.pending[resource_id].fence)
        if not waits:
            raise ValueError("resource must have at least one submitted queue use before retirement")
        self.deferred.retire(resource_id, waits)
        resource.retired = True

    def collect(self) -> list[str]:
        released = self.deferred.collect()
        for resource_id in released:
            status = self.streaming.streaming.resources[resource_id].status
            if status == ResourceStatus.RESIDENT:
                self.streaming.streaming.release(resource_id)
            elif status != ResourceStatus.EVICTED:
                raise RuntimeError("retired resource reached collection in an invalid state")
            del self.resources[resource_id]
        return released

    def snapshot(self) -> dict:
        return {
            "budget_bytes": self.streaming.streaming.budget_bytes,
            "used_bytes": self.streaming.streaming.used_bytes,
            "available_bytes": self.streaming.streaming.available_bytes,
            "queues": self.queues.snapshot(),
            "resources": {
                key: {
                    "size_bytes": value.size_bytes,
                    "state": self.states.state_of(key).value,
                    "last_use": {
                        name: point.value for name, point in sorted(value.last_use.items())
                    },
                    "retired": value.retired,
                    "stream_status": self.streaming.streaming.resources[key].status.value,
                }
                for key, value in sorted(self.resources.items())
            },
            "streaming": self.streaming.snapshot(),
            "deferred_release": self.deferred.snapshot(),
            "simulation_only": True,
            "gpu_commands_executed": False,
            "gpu_resources_created_or_destroyed": False,
        }

    def _active(self, resource_id: str) -> ManagedResource:
        try:
            resource = self.resources[resource_id]
        except KeyError as exc:
            raise KeyError(f"unknown resource: {resource_id}") from exc
        if resource.retired:
            raise RuntimeError("resource has been retired and cannot be used")
        return resource

    def _require_resident(self, resource_id: str) -> None:
        status = self.streaming.streaming.resources[resource_id].status
        if status != ResourceStatus.RESIDENT:
            raise RuntimeError(f"resource is not ready for GPU use: {status.value}")
