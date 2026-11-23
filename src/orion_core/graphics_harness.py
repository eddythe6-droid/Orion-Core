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


class ResourceState(str, Enum):
    """Small explicit subset of D3D12-style resource states for simulation."""

    COMMON = "common"
    COPY_SOURCE = "copy_source"
    COPY_DEST = "copy_dest"
    SHADER_RESOURCE = "shader_resource"
    UNORDERED_ACCESS = "unordered_access"
    RENDER_TARGET = "render_target"
    PRESENT = "present"


@dataclass(frozen=True, slots=True)
class TransitionBarrier:
    resource_id: str
    before: ResourceState
    after: ResourceState


class ResourceStateTracker:
    """Validate explicit resource-state transitions in a deterministic simulation.

    This models only per-resource transition bookkeeping. It does not model
    command-list execution, subresources, split barriers, aliasing barriers,
    queue ownership, implicit promotion/decay, or GPU memory visibility.
    """

    def __init__(self) -> None:
        self._states: dict[str, ResourceState] = {}
        self._history: list[TransitionBarrier] = []

    @property
    def history(self) -> tuple[TransitionBarrier, ...]:
        return tuple(self._history)

    def register(self, resource_id: str, initial_state: ResourceState) -> None:
        if not resource_id or resource_id in self._states:
            raise ValueError("resource id must be non-empty and unique")
        if not isinstance(initial_state, ResourceState):
            raise TypeError("initial_state must be a ResourceState")
        self._states[resource_id] = initial_state

    def state_of(self, resource_id: str) -> ResourceState:
        try:
            return self._states[resource_id]
        except KeyError as exc:
            raise KeyError(f"unknown resource: {resource_id}") from exc

    def transition(
        self,
        resource_id: str,
        before: ResourceState,
        after: ResourceState,
    ) -> TransitionBarrier:
        current = self.state_of(resource_id)
        if not isinstance(before, ResourceState) or not isinstance(after, ResourceState):
            raise TypeError("barrier states must be ResourceState values")
        if current != before:
            raise ValueError(
                f"barrier before-state mismatch for {resource_id}: "
                f"tracked={current.value}, supplied={before.value}"
            )
        if before == after:
            raise ValueError("no-op transition barriers are not supported")
        barrier = TransitionBarrier(resource_id, before, after)
        self._states[resource_id] = after
        self._history.append(barrier)
        return barrier


@dataclass(frozen=True, slots=True)
class SubresourceTransitionBarrier:
    """A simulated transition for one subresource or every subresource."""

    resource_id: str
    subresource: int | None
    before: ResourceState
    after: ResourceState


class SubresourceStateTracker:
    """Track explicit states independently for each resource subresource.

    This is a deterministic CPU-side model. It does not model D3D12 implicit
    promotion/decay, split or aliasing barriers, queue ownership, or execution.
    """

    ALL_SUBRESOURCES = None

    def __init__(self) -> None:
        self._states: dict[str, list[ResourceState]] = {}
        self._history: list[SubresourceTransitionBarrier] = []

    @property
    def history(self) -> tuple[SubresourceTransitionBarrier, ...]:
        return tuple(self._history)

    def register(
        self, resource_id: str, subresource_count: int,
        initial_state: ResourceState,
    ) -> None:
        if not resource_id or resource_id in self._states:
            raise ValueError("resource id must be non-empty and unique")
        if not isinstance(subresource_count, int) or isinstance(subresource_count, bool) or subresource_count <= 0:
            raise ValueError("subresource_count must be a positive integer")
        if not isinstance(initial_state, ResourceState):
            raise TypeError("initial_state must be a ResourceState")
        self._states[resource_id] = [initial_state] * subresource_count

    def subresource_count(self, resource_id: str) -> int:
        return len(self._get(resource_id))

    def state_of(
        self, resource_id: str, subresource: int | None = None,
    ) -> ResourceState | tuple[ResourceState, ...]:
        states = self._get(resource_id)
        if subresource is None:
            return tuple(states)
        self._validate_index(subresource, len(states))
        return states[subresource]

    def transition(
        self, resource_id: str, before: ResourceState, after: ResourceState,
        subresource: int | None = None,
    ) -> SubresourceTransitionBarrier:
        states = self._get(resource_id)
        if not isinstance(before, ResourceState) or not isinstance(after, ResourceState):
            raise TypeError("barrier states must be ResourceState values")
        if before == after:
            raise ValueError("no-op transition barriers are not supported")
        indices = range(len(states)) if subresource is None else (subresource,)
        for index in indices:
            self._validate_index(index, len(states))
            if states[index] != before:
                raise ValueError(
                    f"barrier before-state mismatch for {resource_id}[{index}]: "
                    f"tracked={states[index].value}, supplied={before.value}"
                )
        for index in indices:
            states[index] = after
        barrier = SubresourceTransitionBarrier(resource_id, subresource, before, after)
        self._history.append(barrier)
        return barrier

    def _get(self, resource_id: str) -> list[ResourceState]:
        try:
            return self._states[resource_id]
        except KeyError as exc:
            raise KeyError(f"unknown resource: {resource_id}") from exc

    @staticmethod
    def _validate_index(index: int, count: int) -> None:
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError("subresource index must be an integer")
        if index < 0 or index >= count:
            raise IndexError("subresource index out of range")
