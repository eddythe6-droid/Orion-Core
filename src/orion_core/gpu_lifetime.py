"""Multi-queue fence tracking and deferred resource retirement simulation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .graphics_harness import FencePoint, QueueTimeline


@dataclass(slots=True)
class QueueSet:
    """Named independent queue timelines; completion is tracked per queue."""
    queues: dict[str, QueueTimeline] = field(default_factory=dict)

    def add(self, name: str) -> QueueTimeline:
        if name in self.queues:
            raise ValueError(f"queue already exists: {name}")
        timeline = QueueTimeline(name)
        self.queues[name] = timeline
        return timeline

    def get(self, name: str) -> QueueTimeline:
        try:
            return self.queues[name]
        except KeyError as exc:
            raise KeyError(f"unknown queue: {name}") from exc

    def submit(self, name: str) -> FencePoint:
        return self.get(name).submit()

    def complete(self, name: str, value: int) -> None:
        self.get(name).complete(value)

    def is_complete(self, point: FencePoint) -> bool:
        return self.get(point.queue).has_completed(point)

    def snapshot(self) -> dict:
        return {
            name: {"submitted": queue.submitted, "completed": queue.completed}
            for name, queue in sorted(self.queues.items())
        }


@dataclass(frozen=True, slots=True)
class RetiredResource:
    resource_id: str
    waits_for: tuple[FencePoint, ...]


@dataclass(slots=True)
class DeferredReleaseQueue:
    """Releases simulated resources only after every recorded queue use completes."""
    queues: QueueSet
    pending: list[RetiredResource] = field(default_factory=list)
    released: list[str] = field(default_factory=list)

    def retire(self, resource_id: str, after: Iterable[FencePoint]) -> RetiredResource:
        if not resource_id or any(
            item.resource_id == resource_id for item in self.pending
        ) or resource_id in self.released:
            raise ValueError("resource_id must be non-empty and not already retired")
        points = tuple(after)
        if not points:
            raise ValueError("at least one queue fence point is required")
        for point in points:
            queue = self.queues.get(point.queue)
            if point.value <= 0 or point.value > queue.submitted:
                raise ValueError("retirement fence must refer to submitted queue work")
        item = RetiredResource(resource_id, points)
        self.pending.append(item)
        return item

    def collect(self) -> list[str]:
        still_pending: list[RetiredResource] = []
        newly_released: list[str] = []
        for item in self.pending:
            if all(self.queues.is_complete(point) for point in item.waits_for):
                newly_released.append(item.resource_id)
            else:
                still_pending.append(item)
        self.pending = still_pending
        self.released.extend(newly_released)
        return newly_released

    def snapshot(self) -> dict:
        return {
            "pending": [
                {"resource_id": item.resource_id,
                 "waits_for": [
                     {"queue": point.queue, "fence_value": point.value}
                     for point in item.waits_for
                 ]}
                for item in self.pending
            ],
            "released": list(self.released),
            "simulation_only": True,
            "gpu_resources_destroyed": False,
        }
