# GPU Resource Manager (simulation)

The `GPUResourceManager` composes the existing resource streamer, copy/graphics/compute queue timelines, resource-state tracker, and deferred-release queue into one lifecycle API.

## Lifecycle

1. `request(id, size, priority)` reserves a streaming request and registers a COMMON state.
2. `submit_next_upload()` schedules a simulated copy operation and returns its fence point.
3. `complete_copy(value)` marks uploads resident only after copy-fence completion.
4. `transition(id, state)` permits state bookkeeping only for resident resources.
5. `submit_use(id, "graphics" | "compute", access="read" | "write")` records queue use and automatically inserts simulated waits for cross-queue write/read hazards. Read-after-read is allowed without a dependency.
6. `retire(id)` prevents further use and records all latest queue-use fences (and a pending copy fence, if any).
7. `wait_for(resource_id, consumer_queue, producer_queue)` is expressed through `submit_use(..., wait_for=(producer_queue,))`; it adds an explicit simulated producer-fence dependency.
8. `complete_queue(name, value)` advances a queue timeline; `collect()` releases streaming budget only after every retirement dependency completes.

The manager intentionally requires at least one submitted queue operation before retirement. It rejects use after retirement and use before upload completion.

## Scope and limitations

This is deterministic CPU-side orchestration for testing lifecycle invariants. It does not create ID3D12Resource objects, allocate real VRAM, record or execute command lists, issue cross-queue GPU waits, execute transition barriers, or destroy GPU objects. Queue fences, explicit cross-queue waits, and resource-state changes are simulated. The manager tracks the latest writer and readers and inserts conservative cross-queue dependencies for read-after-write, write-after-read, and write-after-write hazards. Optional `wait_for=(queue_name,)` adds extra caller-declared dependencies. This is a simplified resource hazard model, not a substitute for a complete D3D12 synchronization/ownership model.
