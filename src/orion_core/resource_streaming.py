"""Deterministic resource-streaming scheduler for compatibility research.

This is a CPU-side simulation. It does not perform file I/O, GPU uploads,
command-list execution, or actual DXGI residency operations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ResourcePriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class ResourceStatus(str, Enum):
    QUEUED = "queued"
    LOADING = "loading"
    UPLOAD_PENDING = "upload_pending"
    RESIDENT = "resident"
    EVICTED = "evicted"
    FAILED = "failed"


@dataclass(slots=True)
class StreamResource:
    resource_id: str
    size_bytes: int
    priority: ResourcePriority = ResourcePriority.NORMAL
    pinned: bool = False
    status: ResourceStatus = ResourceStatus.QUEUED
    last_used_tick: int = 0
    request_tick: int = 0


@dataclass(frozen=True, slots=True)
class StreamingEvent:
    tick: int
    event: str
    resource_id: str
    reason: str = ""


@dataclass(slots=True)
class ResourceStreamingEngine:
    budget_bytes: int
    resources: dict[str, StreamResource] = field(default_factory=dict)
    queue: list[str] = field(default_factory=list)
    events: list[StreamingEvent] = field(default_factory=list)
    tick: int = 0
    _used_bytes: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.budget_bytes, int) or isinstance(self.budget_bytes, bool) or self.budget_bytes < 0:
            raise ValueError("budget_bytes must be a non-negative integer")

    @property
    def used_bytes(self) -> int:
        return self._used_bytes

    @property
    def available_bytes(self) -> int:
        return self.budget_bytes - self._used_bytes

    def request(self, resource_id: str, size_bytes: int,
                priority: ResourcePriority = ResourcePriority.NORMAL,
                *, pinned: bool = False) -> StreamResource:
        if not resource_id or resource_id in self.resources:
            raise ValueError("resource_id must be non-empty and unique")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
            raise ValueError("size_bytes must be a positive integer")
        if not isinstance(priority, ResourcePriority):
            raise ValueError("priority must be a ResourcePriority")
        self.tick += 1
        resource = StreamResource(resource_id, size_bytes, priority, pinned,
                                  ResourceStatus.QUEUED, self.tick, self.tick)
        self.resources[resource_id] = resource
        self.queue.append(resource_id)
        self._sort_queue()
        self.events.append(StreamingEvent(self.tick, "requested", resource_id, priority.name.lower()))
        return resource

    def _sort_queue(self) -> None:
        self.queue.sort(key=lambda rid: (
            -int(self.resources[rid].priority),
            self.resources[rid].request_tick,
            rid,
        ))

    def touch(self, resource_id: str) -> None:
        resource = self._get(resource_id)
        if resource.status != ResourceStatus.RESIDENT:
            raise ValueError("only resident resources can be touched")
        self.tick += 1
        resource.last_used_tick = self.tick
        self.events.append(StreamingEvent(self.tick, "used", resource_id))

    def process_next(self) -> StreamResource | None:
        """Start and complete one simulated stream request, or return None."""
        while self.queue:
            resource_id = self.queue.pop(0)
            resource = self.resources[resource_id]
            if resource.status not in (ResourceStatus.QUEUED, ResourceStatus.EVICTED):
                continue
            resource.status = ResourceStatus.LOADING
            self.tick += 1
            self.events.append(StreamingEvent(self.tick, "load_started", resource_id))
            if resource.size_bytes > self.budget_bytes:
                resource.status = ResourceStatus.FAILED
                self.events.append(StreamingEvent(self.tick, "load_failed", resource_id, "larger_than_budget"))
                return resource
            self._make_room(resource)
            if resource.size_bytes > self.available_bytes:
                resource.status = ResourceStatus.FAILED
                self.events.append(StreamingEvent(self.tick, "load_failed", resource_id, "no_evictable_capacity"))
                return resource
            self._used_bytes += resource.size_bytes
            resource.status = ResourceStatus.RESIDENT
            resource.last_used_tick = self.tick
            self.events.append(StreamingEvent(self.tick, "resident", resource_id))
            return resource
        return None

    def process_all(self) -> list[StreamResource]:
        results = []
        while self.queue:
            item = self.process_next()
            if item is not None:
                results.append(item)
        return results

    def _make_room(self, incoming: StreamResource) -> None:
        while incoming.size_bytes > self.available_bytes:
            candidates = [
                item for item in self.resources.values()
                if item.status == ResourceStatus.RESIDENT
                and not item.pinned
                and item.priority < incoming.priority
            ]
            if not candidates:
                return
            victim = min(candidates, key=lambda item: (
                int(item.priority), item.last_used_tick, item.request_tick, item.resource_id
            ))
            self._used_bytes -= victim.size_bytes
            victim.status = ResourceStatus.EVICTED
            self.events.append(StreamingEvent(self.tick, "evicted", victim.resource_id,
                                              f"preempted_by:{incoming.resource_id}"))

    def release(self, resource_id: str) -> int:
        resource = self._get(resource_id)
        if resource.status != ResourceStatus.RESIDENT:
            raise ValueError("only resident resources can be released")
        self._used_bytes -= resource.size_bytes
        resource.status = ResourceStatus.EVICTED
        self.tick += 1
        self.events.append(StreamingEvent(self.tick, "released", resource_id))
        return resource.size_bytes

    def snapshot(self) -> dict:
        return {
            "budget_bytes": self.budget_bytes,
            "used_bytes": self.used_bytes,
            "available_bytes": self.available_bytes,
            "queued": list(self.queue),
            "resources": {
                key: {
                    "size_bytes": value.size_bytes,
                    "priority": value.priority.name.lower(),
                    "pinned": value.pinned,
                    "status": value.status.value,
                    "last_used_tick": value.last_used_tick,
                }
                for key, value in sorted(self.resources.items())
            },
            "events": [
                {"tick": event.tick, "event": event.event,
                 "resource_id": event.resource_id, "reason": event.reason}
                for event in self.events
            ],
            "simulation_only": True,
            "gpu_upload_performed": False,
        }

    def _get(self, resource_id: str) -> StreamResource:
        try:
            return self.resources[resource_id]
        except KeyError as exc:
            raise KeyError(f"unknown resource: {resource_id}") from exc
