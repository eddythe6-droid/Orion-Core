# Graphics dependency assessment

Game Inspector attaches a `graphics_assessment` object to each valid PE dependency report.

## Evidence collected

- Exact imported DLL names for a curated set of Direct3D 12/11, DXGI, Vulkan, OpenGL, shader compiler/runtime, and selected vendor modules.
- A small set of exact graphics entry-point names, classified only when observed in the matching import module.
- Inventory paths with shader-like and texture-like extensions. Only file names/extensions are considered; files are not decoded.

## Interpretation

`graphics_dependencies_observed` means that at least one recognized graphics DLL appears in a PE import table. It does not prove the code path executes. A static import list also misses APIs loaded dynamically. The per-module confidence label describes the strength of the module-name classification, not compatibility confidence.

Shader/texture extension counts are inventory hints, not validated asset counts. No shader bytecode, DXIL/DXBC container, root signature, PSO, resource binding, GPU feature level, or Xbox GDK ABI is validated by this step.

The report always sets `compatibility_established` and `execution_performed` to false. It is a triage aid, not a porting verdict.
