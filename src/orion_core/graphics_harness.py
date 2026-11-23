"""Deterministic, hardware-independent models for graphics lifetime tests.

These simulators are not GPU drivers and do not claim to reproduce Xbox internals.
They model a small set of explicit invariants useful for testing our own abstractions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


@dataclass(frozen=True, slots=True)
class FencePoint:
    queue: str
    value: int


class QueueTimeline:
    """A monotonic command-queue timeline with explicit completion."""

    def __init__(self, name: str) -> None:
        if not name.strip():
            raise ValueError("queue name must not be empty")
        self.name = name
        self._submitted = 0
        self._completed = 0

    @property
    def submitted(self) -> int:
        return self._submitted

    @property
    def completed(self) -> int:
        return self._completed

    def submit(self) -> FencePoint:
        self._submitted += 1
        return FencePoint(self.name, self._submitted)

    def complete(self, value: int) -> None:
        if value < self._completed or value > self._submitted:
            raise ValueError("completion must be monotonic and no greater than submitted work")
        self._completed = value

    def has_completed(self, point: FencePoint) -> bool:
        if point.queue != self.name:
            raise ValueError("fence point belongs to another queue")
        return self._completed >= point.value

    def require_completed(self, point: FencePoint) -> None:
        if not self.has_completed(point):
            raise RuntimeError(f"GPU work {point.queue}:{point.value} is still in flight")


class ResidencyState(str, Enum):
    NON_RESIDENT = "non_resident"
    RESIDENT = "resident"


@dataclass(slots=True)
class MemoryAllocation:
    allocation_id: str
    size_bytes: int
    state: ResidencyState = ResidencyState.NON_RESIDENT


class ResidencyBudget:
    """Simple pool budget model; it does not emulate OS/driver residency policy."""

    def __init__(self, budget_bytes: int) -> None:
        if budget_bytes < 0:
            raise ValueError("budget_bytes must be non-negative")
        self.budget_bytes = budget_bytes
        self._allocations: dict[str, MemoryAllocation] = {}

    @property
    def resident_bytes(self) -> int:
        return sum(a.size_bytes for a in self._allocations.values()
                   if a.state == ResidencyState.RESIDENT)

    def add(self, allocation_id: str, size_bytes: int) -> MemoryAllocation:
        if not allocation_id or allocation_id in self._allocations:
            raise ValueError("allocation id must be non-empty and unique")
        if size_bytes <= 0:
            raise ValueError("allocation size must be positive")
        allocation = MemoryAllocation(allocation_id, size_bytes)
        self._allocations[allocation_id] = allocation
        return allocation

    def make_resident(self, allocation_id: str) -> None:
        allocation = self._get(allocation_id)
        if allocation.state == ResidencyState.RESIDENT:
            return
        if self.resident_bytes + allocation.size_bytes > self.budget_bytes:
            raise MemoryError("residency budget exceeded")
        allocation.state = ResidencyState.RESIDENT

    def evict(self, allocation_id: str) -> None:
        self._get(allocation_id).state = ResidencyState.NON_RESIDENT

    def _get(self, allocation_id: str) -> MemoryAllocation:
        try:
            return self._allocations[allocation_id]
        except KeyError as exc:
            raise KeyError(f"unknown allocation: {allocation_id}") from exc


@dataclass(frozen=True, slots=True)
class DescriptorRange:
    start: int
    count: int


@dataclass(slots=True)
class _RetiredRange:
    descriptor_range: DescriptorRange
    fence_point: FencePoint


class DescriptorAllocator:
    """Linear descriptor heap allocator with fence-delayed range reuse."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("descriptor capacity must be positive")
        self.capacity = capacity
        self._active: set[int] = set()
        self._retired: list[_RetiredRange] = []
        self._next = 0

    def allocate(self, count: int) -> DescriptorRange:
        if count <= 0:
            raise ValueError("descriptor count must be positive")
        for start in range(self.capacity - count + 1):
            slots = set(range(start, start + count))
            if not (slots & self._active) and not any(
                slots & set(range(r.descriptor_range.start,
                                  r.descriptor_range.start + r.descriptor_range.count))
                for r in self._retired
            ):
                self._active.update(slots)
                self._next = max(self._next, start + count)
                return DescriptorRange(start, count)
        raise MemoryError("descriptor heap exhausted")

    def retire(self, descriptor_range: DescriptorRange, after: FencePoint) -> None:
        slots = set(range(descriptor_range.start,
                          descriptor_range.start + descriptor_range.count))
        if not slots or not slots.issubset(self._active):
            raise ValueError("range is not fully active in this allocator")
        self._active.difference_update(slots)
        self._retired.append(_RetiredRange(descriptor_range, after))

    def collect(self, completed: Iterable[FencePoint]) -> int:
        done = {(p.queue, p.value) for p in completed}
        keep: list[_RetiredRange] = []
        released = 0
        for item in self._retired:
            key = (item.fence_point.queue, item.fence_point.value)
            if any(q == key[0] and v >= key[1] for q, v in done):
                released += item.descriptor_range.count
            else:
                keep.append(item)
        self._retired = keep
        return released
