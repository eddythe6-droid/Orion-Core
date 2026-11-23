# Root-signature layout research

Orion-Core now provides a declarative root-signature model. It estimates root
parameter DWORD cost, validates supported parameter kinds and visibility labels,
checks descriptor-table ranges, and rejects layouts exceeding the 64-DWORD
root-signature cost limit.

This is not native D3D12 serialization or driver validation. Register overlap,
static sampler definitions, versioned root-signature flags, root-signature
version negotiation, descriptor heap creation, and command-list binding remain
outside the model. A valid description is labelled `native_validation_needed`.

The resource-binding tier assessor accepts both normalized labels such as
`tier_2` and the numeric strings emitted by the native probe (`2`).
