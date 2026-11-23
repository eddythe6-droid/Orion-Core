"""Resource queue ownership bookkeeping (simulation only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from .graphics_harness import FencePoint


@dataclass(frozen=True, slots=True)
class OwnershipTransfer:
    resource_id: str
    previous_queue: str | None
    next_queue: str
    dependency: FencePoint | None


@dataclass(slots=True)
class ResourceOwnershipTracker:
    """Record the queue currently owning a resource after submitted use."""

    owners: dict[str, str] = field(default_factory=dict)
    history: list[OwnershipTransfer] = field(default_factory=list)

    def register(self, resource_id: str) -> None:
        if not resource_id or resource_id in self.owners:
            raise ValueError("resource id must be non-empty and unique")
        self.owners[resource_id] = ""

    def transfer(self, resource_id: str, next_queue: str,
                 dependency: FencePoint | None) -> OwnershipTransfer:
        if resource_id not in self.owners:
            raise KeyError(f"unknown resource: {resource_id}")
        if not next_queue.strip():
            raise ValueError("next queue must not be empty")
        previous = self.owners[resource_id] or None
        if previous == next_queue:
            raise ValueError("resource is already owned by the requested queue")
        if previous is not None and dependency is None:
            raise ValueError("cross-queue ownership transfer requires a dependency fence")
        if dependency is not None and dependency.queue != previous:
            raise ValueError("ownership dependency must belong to the previous owner queue")
        item = OwnershipTransfer(resource_id, previous, next_queue, dependency)
        self.owners[resource_id] = next_queue
        self.history.append(item)
        return item

    def owner_of(self, resource_id: str) -> str | None:
        try:
            return self.owners[resource_id] or None
        except KeyError as exc:
            raise KeyError(f"unknown resource: {resource_id}") from exc

    def snapshot(self) -> dict:
        return {
            "owners": {key: value or None for key, value in sorted(self.owners.items())},
            "transfers": [
                {
                    "resource_id": item.resource_id,
                    "previous_queue": item.previous_queue,
                    "next_queue": item.next_queue,
                    "dependency": (
                        {"queue": item.dependency.queue, "fence_value": item.dependency.value}
                        if item.dependency else None
                    ),
                }
                for item in self.history
            ],
            "simulation_only": True,
            "gpu_ownership_transfers_executed": False,
        }
