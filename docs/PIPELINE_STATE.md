# Pipeline state research model

Orion-Core represents a declarative graphics pipeline description and performs
structural consistency checks. It validates stage combinations, topology labels,
sample-count shape, render-target count, input-layout usage, and depth-state
requirements.

A structurally valid description receives `hardware_validation_needed`.
This is intentional: actual D3D12 PSO creation depends on complete native state,
shader bytecode, root signature, device/driver support, and runtime validation.
The model does not create a PSO and does not establish driver acceptance.

# Shader feature requirements

`assess_shader_requirements` compares explicit feature requirements against
fields reported by the native D3D12 probe. Missing or unrecognized values remain
`unknown`; a known lower tier or unavailable required boolean feature is
`not_satisfied`. The result is limited to feature declarations: no bytecode
inspection, shader compilation, workload execution, or Xbox D3D12.x inference.
