"""Explicit inter-queue wait and ownership simulation.

This models queue-level dependencies using submitted fence points. It does not
issue D3D12 queue waits or execute GPU work.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .gpu_lifetime import QueueSet
from .graphics_harness import FencePoint


@dataclass(frozen=True, slots=True)
class QueueWait:
    consumer_queue: str
    producer_fence: FencePoint


@dataclass(slots=True)
class QueueSynchronizer:
    """Track explicit producer-fence waits before consumer queue submissions."""

    queues: QueueSet
    _waits: dict[str, list[FencePoint]] = field(default_factory=dict)
    _history: list[QueueWait] = field(default_factory=list)

    @property
    def history(self) -> tuple[QueueWait, ...]:
        return tuple(self._history)

    def wait(self, consumer_queue: str, producer_fence: FencePoint) -> QueueWait:
        consumer = self.queues.get(consumer_queue)
        producer = self.queues.get(producer_fence.queue)
        if consumer_queue == producer_fence.queue:
            raise ValueError("a queue cannot wait on its own fence in this model")
        if producer_fence.value <= 0 or producer_fence.value > producer.submitted:
            raise ValueError("wait must reference already submitted producer work")
        if producer.has_completed(producer_fence):
            # A completed dependency is already satisfied; no wait needs to be queued.
            return QueueWait(consumer_queue, producer_fence)
        pending = self._waits.setdefault(consumer_queue, [])
        if producer_fence not in pending:
            self._assert_no_cycle(consumer_queue, producer_fence.queue)
            pending.append(producer_fence)
        item = QueueWait(consumer_queue, producer_fence)
        self._history.append(item)
        return item

    def submit(self, queue_name: str) -> FencePoint:
        """Submit simulated consumer work; queued waits remain its prerequisites."""
        self.queues.get(queue_name)
        return self.queues.submit(queue_name)

    def complete(self, queue_name: str, value: int) -> None:
        queue = self.queues.get(queue_name)
        if value < queue.completed or value > queue.submitted:
            raise ValueError("completion must be monotonic and no greater than submitted work")
        blocked = [
            point for point in self._waits.get(queue_name, [])
            if not self.queues.is_complete(point)
        ]
        if blocked and value > queue.completed:
            details = ", ".join(f"{p.queue}:{p.value}" for p in blocked)
            raise RuntimeError(f"queue {queue_name} is waiting for producer fence(s): {details}")
        queue.complete(value)
        self._prune_completed_waits()

    def can_submit_use(self, queue_name: str, producer_fence: FencePoint) -> bool:
        """Whether producer work is complete or an explicit wait is queued."""
        self.queues.get(queue_name)
        self.queues.get(producer_fence.queue)
        return (
            self.queues.is_complete(producer_fence)
            or producer_fence in self._waits.get(queue_name, [])
        )

    def snapshot(self) -> dict:
        return {
            "pending_waits": {
                name: [
                    {"producer_queue": point.queue, "fence_value": point.value}
                    for point in points
                ]
                for name, points in sorted(self._waits.items()) if points
            },
            "wait_count": len(self._history),
            "simulation_only": True,
            "gpu_queue_waits_issued": False,
        }

    def _prune_completed_waits(self) -> None:
        for name, points in self._waits.items():
            self._waits[name] = [
                point for point in points if not self.queues.is_complete(point)
            ]

    def _assert_no_cycle(self, consumer: str, producer: str) -> None:
        # An edge producer -> consumer means consumer depends on producer.
        graph: dict[str, set[str]] = {}
        for target, points in self._waits.items():
            for point in points:
                graph.setdefault(point.queue, set()).add(target)
        graph.setdefault(producer, set()).add(consumer)

        stack = [consumer]
        visited: set[str] = set()
        while stack:
            node = stack.pop()
            if node == producer:
                raise ValueError("queue wait would create a dependency cycle")
            if node in visited:
                continue
            visited.add(node)
            stack.extend(graph.get(node, ()))
