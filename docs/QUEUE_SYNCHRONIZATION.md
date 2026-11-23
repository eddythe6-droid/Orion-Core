# Queue synchronization model (simulation)

`QueueSynchronizer` adds explicit producer-fence waits across named queues.
A consumer queue can enqueue a wait on an already-submitted producer fence;
consumer completion is rejected until that producer fence has completed.
Completed producer fences need no queued wait. Self-waits, unknown queues,
unsubmitted fence values, and dependency cycles are rejected.

The model uses a conservative queue-level dependency graph. It does not
represent individual command-list boundaries, D3D12 queue Wait/Signal calls,
GPU scheduling, resource ownership transfers, or actual memory visibility.
A successful test proves only the simulator's bookkeeping invariants.

Example:

1. Submit copy work and obtain its fence point.
2. Enqueue a graphics-queue wait on that copy fence.
3. Submit graphics work.
4. Complete the copy fence, then complete graphics work.

The wait is a simulated prerequisite, not an executed GPU synchronization.
