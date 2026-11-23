# Diagnostic report format

The normal JSON diagnostic command emits a versioned report envelope:

```powershell
python -m orion_core --json
python -m orion_core --json --basic-only
```

The report includes:

- `report_schema_version`: schema identifier for downstream consumers.
- `generated_at`: UTC timestamp in ISO 8601 format.
- `collector`: Orion-Core name and package version.
- `environment`: Python version and implementation.
- `system`: read-only operating-system, CPU-count, architecture and memory inventory.
- `windows_diagnostics`: read-only Windows CPU/GPU and graphics-runtime inventory, or an explicit skipped/unsupported result.
- `validation`: scope notes and an explicit flag that hardware runtime tests were not performed by this collector.

## Stability and privacy

The report schema is versioned independently of the package version. Consumers should check
`report_schema_version` before relying on field names. A future incompatible schema
change must increment the major schema version and document the migration.

The current collector avoids serial numbers, device identifiers, usernames, and
filesystem paths. GPU/driver inventory is descriptive; it does not prove a
particular feature level, benchmark performance, or game compatibility.
