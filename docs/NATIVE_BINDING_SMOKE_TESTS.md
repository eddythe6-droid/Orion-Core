# Native root-signature and descriptor-heap smoke tests

The Windows D3D12 probe now performs a minimal runtime smoke test per adapter:

- serializes an empty version-1.0 root signature with the input-assembler flag;
- creates the root signature on the device;
- creates a shader-visible CBV/SRV/UAV descriptor heap (16 slots);
- creates a shader-visible sampler descriptor heap (8 slots);
- records descriptor increment sizes reported by the device.

The JSON fields are `root_signature_smoke_test`,
`resource_descriptor_heap_smoke_test`, `sampler_descriptor_heap_smoke_test`,
`resource_descriptor_increment`, `sampler_descriptor_increment`, and
`binding_smoke_note`.

These tests establish only that the driver accepted these minimal objects.
They do not create a graphics PSO, populate descriptors, bind heaps to a command
list, validate root parameters against shaders, or execute a draw/dispatch.
A successful compile in Windows CI is not a runtime hardware result.
