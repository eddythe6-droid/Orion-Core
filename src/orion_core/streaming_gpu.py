"""Fence-aware GPU upload lifecycle simulation built on the resource streamer.

This module models the lifetime boundary between reserving streaming memory,
submitting a simulated copy-queue operation, and observing its fence completion.
It does not create D3D12 resources or execute GPU commands.
"""
from __future__ import annotations

from dataclasses import dataclass

from .graphics_harness import FencePoint, QueueTimeline
from .resource_streaming import ResourcePriority, ResourceStatus, ResourceStreamingEngine, StreamResource, StreamingEvent


@dataclass(frozen=True, slots=True)
class PendingUpload:
    resource_id: str
    fence: FencePoint


class FenceAwareStreamingEngine:
    """Coordinates stream allocation and a monotonic simulated copy-queue fence."""

    def __init__(self, budget_bytes: int, queue_name: str = "copy") -> None:
        self.streaming = ResourceStreamingEngine(budget_bytes)
        self.copy_queue = QueueTimeline(queue_name)
        self.pending: dict[str, PendingUpload] = {}

    def request(self, resource_id: str, size_bytes: int,
                priority: ResourcePriority = ResourcePriority.NORMAL,
                *, pinned: bool = False) -> StreamResource:
        return self.streaming.request(resource_id, size_bytes, priority, pinned=pinned)

    def submit_next_upload(self) -> PendingUpload | None:
        resource = self.streaming.process_next()
        if resource is None or resource.status != ResourceStatus.RESIDENT:
            return None
        # The base model reserves memory on stream completion. Until the fence
        # completes, protect the allocation from normal use and eviction.
        resource.status = ResourceStatus.UPLOAD_PENDING
        fence = self.copy_queue.submit()
        pending = PendingUpload(resource.resource_id, fence)
        self.pending[resource.resource_id] = pending
        self.streaming.events.append(
            StreamingEvent(
                self.streaming.tick, "upload_submitted", resource.resource_id,
                f"{fence.queue}:{fence.value}"
            )
        )
        return pending

    def complete_uploads(self, completed_value: int) -> list[str]:
        self.copy_queue.complete(completed_value)
        completed: list[str] = []
        for resource_id, pending in list(self.pending.items()):
            if self.copy_queue.has_completed(pending.fence):
                resource = self.streaming.resources[resource_id]
                resource.status = ResourceStatus.RESIDENT
                resource.last_used_tick = self.streaming.tick
                self.streaming.events.append(
                    StreamingEvent(
                        self.streaming.tick, "upload_completed", resource_id,
                        f"{pending.fence.queue}:{pending.fence.value}"
                    )
                )
                completed.append(resource_id)
                del self.pending[resource_id]
        return completed

    def touch(self, resource_id: str) -> None:
        if resource_id in self.pending:
            raise RuntimeError("resource upload is still in flight")
        self.streaming.touch(resource_id)

    def snapshot(self) -> dict:
        return {
            "streaming": self.streaming.snapshot(),
            "copy_queue": {
                "name": self.copy_queue.name,
                "submitted": self.copy_queue.submitted,
                "completed": self.copy_queue.completed,
            },
            "pending_uploads": {
                key: {"queue": value.fence.queue, "fence_value": value.fence.value}
                for key, value in sorted(self.pending.items())
            },
            "simulation_only": True,
            "gpu_commands_executed": False,
        }
