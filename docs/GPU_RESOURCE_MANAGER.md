# GPU Resource Manager (simulation)

The `GPUResourceManager` composes the existing resource streamer, copy/graphics/compute queue timelines, resource-state tracker, and deferred-release queue into one lifecycle API.

## Lifecycle

1. `request(id, size, priority)` reserves a streaming request and registers a COMMON state.
2. `submit_next_upload()` schedules a simulated copy operation and returns its fence point.
3. `complete_copy(value)` marks uploads resident only after copy-fence completion.
4. `transition(id, state)` permits state bookkeeping only for resident resources.
5. `submit_use(id, "graphics" | "compute")` records the latest submitted use on that queue.
6. `retire(id)` prevents further use and records all latest queue-use fences (and a pending copy fence, if any).
7. `complete_queue(name, value)` advances a queue timeline; `collect()` releases streaming budget only after every retirement dependency completes.

The manager intentionally requires at least one submitted queue operation before retirement. It rejects use after retirement and use before upload completion.

## Scope and limitations

This is deterministic CPU-side orchestration for testing lifecycle invariants. It does not create ID3D12Resource objects, allocate real VRAM, record or execute command lists, issue cross-queue GPU waits, execute transition barriers, or destroy GPU objects. Queue fences and resource-state changes are simulated. The model tracks one latest fence per queue; it is not a substitute for a complete D3D12 synchronization/ownership model.
