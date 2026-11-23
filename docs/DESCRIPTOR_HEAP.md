# Descriptor heap manager (simulation)

`DescriptorHeapManager` allocates contiguous ranges in a fixed-capacity descriptor
heap model. Retiring a range requires one or more already-submitted queue fence
points. The slots remain unavailable until every queue dependency completes;
only then does `collect()` make the range reusable.

The manager rejects duplicate allocation IDs, invalid counts, unknown queues,
and fence values that have not been submitted. The implementation is a CPU-side
allocator model only: it does not create a D3D12 descriptor heap, write descriptors,
manage CPU/GPU descriptor handles, or inspect command lists. It also does not
implement shader-visible heap switching or descriptor copying.
