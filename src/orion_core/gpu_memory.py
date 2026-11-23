"""GPU memory budget analysis and deterministic pressure simulation.

The analyzer distinguishes reported DXGI budget/usage from synthetic pool
simulations. It does not allocate GPU memory or predict driver eviction policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MemoryPressure(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    OVER_BUDGET = "over_budget"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MemoryPoolSnapshot:
    segment: str
    budget_bytes: int | None
    usage_bytes: int | None
    available_bytes: int | None
    utilization: float | None
    pressure: MemoryPressure


def analyze_memory_pool(segment: str, budget_bytes: int | None,
                        usage_bytes: int | None) -> MemoryPoolSnapshot:
    """Analyze a DXGI-style budget and current usage without guessing missing data."""
    if not segment.strip():
        raise ValueError("segment must not be empty")
    for label, value in (("budget_bytes", budget_bytes), ("usage_bytes", usage_bytes)):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            raise ValueError(f"{label} must be a non-negative integer or None")
    if budget_bytes is None or usage_bytes is None or budget_bytes == 0:
        return MemoryPoolSnapshot(segment, budget_bytes, usage_bytes, None, None, MemoryPressure.UNKNOWN)
    available = max(0, budget_bytes - usage_bytes)
    ratio = usage_bytes / budget_bytes
    if usage_bytes > budget_bytes:
        pressure = MemoryPressure.OVER_BUDGET
    elif ratio >= 0.90:
        pressure = MemoryPressure.HIGH
    elif ratio >= 0.70:
        pressure = MemoryPressure.MODERATE
    else:
        pressure = MemoryPressure.LOW
    return MemoryPoolSnapshot(segment, budget_bytes, usage_bytes, available,
                              ratio, pressure)


class SimulatedMemoryPool:
    """Simple deterministic allocation pool; not a model of real driver residency."""

    def __init__(self, capacity_bytes: int) -> None:
        if not isinstance(capacity_bytes, int) or isinstance(capacity_bytes, bool) or capacity_bytes < 0:
            raise ValueError("capacity_bytes must be a non-negative integer")
        self.capacity_bytes = capacity_bytes
        self._allocations: dict[str, int] = {}

    @property
    def used_bytes(self) -> int:
        return sum(self._allocations.values())

    @property
    def available_bytes(self) -> int:
        return self.capacity_bytes - self.used_bytes

    def allocate(self, allocation_id: str, size_bytes: int) -> None:
        if not allocation_id or allocation_id in self._allocations:
            raise ValueError("allocation id must be non-empty and unique")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
            raise ValueError("size_bytes must be a positive integer")
        if size_bytes > self.available_bytes:
            raise MemoryError("simulated GPU memory pool exhausted")
        self._allocations[allocation_id] = size_bytes

    def release(self, allocation_id: str) -> int:
        try:
            return self._allocations.pop(allocation_id)
        except KeyError as exc:
            raise KeyError(f"unknown allocation: {allocation_id}") from exc

    def snapshot(self, segment: str = "simulated_local") -> MemoryPoolSnapshot:
        return analyze_memory_pool(segment, self.capacity_bytes, self.used_bytes)


def analyze_probe_memory(adapter: dict[str, Any]) -> dict[str, Any]:
    """Analyze local/non-local DXGI memory records embedded in a probe adapter."""
    memory = adapter.get("video_memory")
    if not isinstance(memory, dict):
        memory = {}
    pools = {}
    for key in ("local", "non_local"):
        record = memory.get(key)
        if not isinstance(record, dict):
            record = {}
        snapshot = analyze_memory_pool(
            key, record.get("budget_bytes"), record.get("current_usage_bytes")
        )
        pools[key] = {
            "budget_bytes": snapshot.budget_bytes,
            "usage_bytes": snapshot.usage_bytes,
            "available_bytes": snapshot.available_bytes,
            "utilization": snapshot.utilization,
            "pressure": snapshot.pressure.value,
        }
    return {
        "adapter": adapter.get("name", "unknown"),
        "pools": pools,
        "interpretation": "DXGI current budget and usage snapshot; values can change dynamically",
        "game_compatibility_established": False,
    }
