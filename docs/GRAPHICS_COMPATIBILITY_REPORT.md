# Unified graphics compatibility report

`build_graphics_compatibility_report` combines four conservative research
sections: declarative pipeline validation, shader feature requirements,
format-query availability/raw masks, and resource-binding tier requirements.

Overall outcomes:
- `requirements_not_met`: a structural pipeline error or a known unmet feature.
- `incomplete_evidence`: at least one required value is unknown.
- `hardware_validation_needed`: declared checks are satisfied or queried, but
  native D3D12 pipeline/workload validation has not been performed.

The report explicitly records that no PSO was created, no shader bytecode was
compiled, no GPU workload was executed, and Xbox/game compatibility was not
established. Empty requirement sections are neutral and do not imply support.
