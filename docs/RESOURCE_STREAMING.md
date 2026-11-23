# Resource streaming research model

## Scope

The Python resource streaming engine is a deterministic, hardware-independent model for studying resource request ordering and memory-pressure policy. It is not a GPU driver, filesystem streamer, Xbox runtime, or D3D12 residency implementation.

## Model

- Requests carry a byte size, priority (low, normal, high, critical), and optional pinning.
- Pending requests are ordered by descending priority, then FIFO request time.
- A processed request transitions through queued, loading, and resident or failed.
- If capacity is insufficient, the engine may evict only unpinned resident resources with strictly lower priority than the incoming request.
- Eviction selects the lowest priority first, then least-recently-used resource.
- Equal/higher-priority and pinned resources are protected.
- Explicit touch updates recency; release removes a resident allocation from the simulated budget.
- Every transition is recorded in an event log and can be exported with snapshot().

## Current limitations

- Loading is synchronous and simulated; no real asynchronous I/O occurs.
- No file formats, decompression, texture transcoding, GPU copy queue, fences, descriptor lifetime, or D3D12 resource creation are involved.
- The model has one abstract memory pool and does not represent heaps, subresources, tiled resources, or per-node memory.
- Eviction policy is a research hypothesis, not a claim about Windows, Xbox, or any particular game's runtime.
- No game compatibility or performance conclusion can be drawn from a simulation.

## Example

```python
from orion_core.resource_streaming import ResourcePriority, ResourceStreamingEngine

engine = ResourceStreamingEngine(budget_bytes=6 * 1024**3)
engine.request("level-textures", 2 * 1024**3, ResourcePriority.HIGH)
engine.request("ambient-audio", 256 * 1024**2, ResourcePriority.NORMAL)
engine.process_all()
print(engine.snapshot())
```

The 6 GiB value is an illustrative simulation budget, not an assumption about the actual DXGI budget on a given PC.
