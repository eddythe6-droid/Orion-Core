# Synthetic graphics harness

The module `orion_core.graphics_harness` contains deterministic models for three explicit-lifetime concepts:

- `QueueTimeline`: monotonic submissions and fence completion.
- `ResidencyBudget`: a configurable byte budget and resident/non-resident transitions.
- `DescriptorAllocator`: heap ranges that cannot be reused until the associated fence point has completed.

These are deliberately small **simulation models**, not a D3D12 implementation, driver, GPU benchmark, or Xbox emulator. They do not model scheduling, physical paging, actual heaps, resource barriers, shader execution, or undocumented console behavior.

Run the tests with:

```bash
python -m pip install -e ".[test]"
python -m pytest -q
```

A later native Windows validation sample should use public D3D12 APIs to query the adapter, create queues/fences, and exercise resource transitions. No native GPU test has been built or run yet.

## Documented PC behavior behind the model

- D3D12 queues expose submission and fence signal/wait operations. See [Microsoft's multi-engine synchronization guide](https://learn.microsoft.com/en-us/windows/win32/direct3d12/user-mode-heap-synchronization).
- Resource barriers communicate per-resource state transitions and synchronization requirements. See [Microsoft's resource barrier guide](https://learn.microsoft.com/en-us/windows/win32/direct3d12/using-resource-barriers-to-synchronize-resource-states-in-direct3d-12).
- Residency budgets fluctuate and should be queried rather than inferred from physical VRAM size. See [Microsoft's residency guide](https://learn.microsoft.com/en-us/windows/win32/direct3d12/residency).
- Descriptor ranges in heaps must not be modified while in-flight GPU work may reference them. See [Microsoft's advanced descriptor table guidance](https://learn.microsoft.com/en-us/windows/win32/direct3d12/advanced-use-of-descriptor-tables).

The simulator captures only selected invariants from these public PC concepts. It does not assert parity with Xbox D3D12.x or any particular game's renderer.


## Resource transition state tracker

The simulator also includes `ResourceStateTracker`, a deterministic bookkeeping model for explicit per-resource transitions. It validates the caller-supplied before-state against the tracked state, records valid transitions, and rejects unknown resources, duplicate registrations, mismatched before-states, and no-op transitions.

This is intentionally not a full D3D12 barrier implementation. It does not model subresources, split barriers, aliasing barriers, UAV ordering, queue ownership, implicit promotion/decay, command-list execution, or GPU memory visibility. A passing simulator test is not evidence of actual driver behavior.


## Multi-queue lifetime model

`orion_core.gpu_lifetime` adds independent named queue timelines (for example, copy, compute, and graphics) and a deferred-release queue. A resource retirement record can depend on several fence points; collection releases the simulated record only after every referenced queue has completed its required value. Unknown queues, duplicate queue names, empty dependencies, and fence points that were never submitted are rejected.

This models a conservative lifetime invariant only. It does not submit D3D12 work, establish real GPU queue waits, manage command allocators, or destroy GPU resources.
