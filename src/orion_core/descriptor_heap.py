"""Fence-aware descriptor heap range management (simulation only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from .gpu_lifetime import QueueSet
from .graphics_harness import DescriptorRange, FencePoint


@dataclass(frozen=True, slots=True)
class RetiredDescriptorRange:
    descriptor_range: DescriptorRange
    waits_for: tuple[FencePoint, ...]


@dataclass(slots=True)
class DescriptorHeapManager:
    """Allocate descriptor slots and delay reuse until all queue users complete."""

    capacity: int
    queues: QueueSet
    active: dict[tuple[int, int], DescriptorRange] = field(default_factory=dict)
    retired: list[RetiredDescriptorRange] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.capacity, int) or isinstance(self.capacity, bool) or self.capacity <= 0:
            raise ValueError("descriptor capacity must be a positive integer")

    def allocate(self, allocation_id: str, count: int) -> DescriptorRange:
        if not allocation_id or allocation_id in self.active:
            raise ValueError("allocation_id must be non-empty and unique")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ValueError("descriptor count must be a positive integer")
        occupied = set()
        for item in self.active.values():
            occupied.update(range(item.start, item.start + item.count))
        for item in self.retired:
            r = item.descriptor_range
            occupied.update(range(r.start, r.start + r.count))
        for start in range(self.capacity - count + 1):
            slots = set(range(start, start + count))
            if not slots.intersection(occupied):
                result = DescriptorRange(start, count)
                self.active[allocation_id] = result
                return result
        raise MemoryError("descriptor heap exhausted")

    def retire(self, allocation_id: str, after: tuple[FencePoint, ...]) -> RetiredDescriptorRange:
        try:
            descriptor_range = self.active[allocation_id]
        except KeyError as exc:
            raise KeyError(f"unknown active descriptor allocation: {allocation_id}") from exc
        waits = tuple(after)
        if not waits:
            raise ValueError("at least one queue fence dependency is required")
        for point in waits:
            queue = self.queues.get(point.queue)
            if point.value <= 0 or point.value > queue.submitted:
                raise ValueError("retirement fence must refer to submitted queue work")
        item = RetiredDescriptorRange(descriptor_range, waits)
        self.retired.append(item)
        del self.active[allocation_id]
        return item

    def collect(self) -> list[DescriptorRange]:
        released: list[DescriptorRange] = []
        keep: list[RetiredDescriptorRange] = []
        for item in self.retired:
            if all(self.queues.is_complete(point) for point in item.waits_for):
                released.append(item.descriptor_range)
            else:
                keep.append(item)
        self.retired = keep
        return released

    def snapshot(self) -> dict:
        return {
            "capacity": self.capacity,
            "active": {
                key: {"start": value.start, "count": value.count}
                for key, value in sorted(self.active.items())
            },
            "retired": [
                {
                    "start": item.descriptor_range.start,
                    "count": item.descriptor_range.count,
                    "waits_for": [
                        {"queue": p.queue, "fence_value": p.value}
                        for p in item.waits_for
                    ],
                }
                for item in self.retired
            ],
            "simulation_only": True,
            "native_descriptor_heap_created": False,
        }
