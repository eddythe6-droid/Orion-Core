# Format and resource-binding research

## Format queries

The native D3D12 probe records `CheckFeatureSupport(D3D12_FEATURE_FORMAT_SUPPORT)`
results as raw `Support1` and `Support2` masks. Orion-Core preserves and
compares these masks but does not decode flags into claims about render-target,
depth-stencil, sampling, typed-UAV, or resolve support. A returned query is
therefore marked `hardware_validation_needed`, not compatible.

## Resource binding

The binding assessment compares an explicit minimum tier with the tier reported
by the native probe. Unknown values remain unknown. This is only a tier-level
check; it does not inspect root signatures, descriptor counts, shader bindings,
heap layouts, or native command-list execution.
