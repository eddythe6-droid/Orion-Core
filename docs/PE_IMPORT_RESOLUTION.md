# Local PE import resolution

Game Inspector can compare a PE file's normal import table with export tables from PE files found elsewhere in the same inspected folder.

## Result states

- `resolved_name_match` / `resolved_ordinal_match`: a local candidate DLL exports the requested name or ordinal.
- `forwarded_export`: the export exists but forwards to another module; the forwarding chain is not followed.
- `missing_module`: no local PE file with the requested DLL basename was indexed.
- `missing_symbol`: a unique local candidate was found and its parsed export table does not contain the requested symbol.
- `ambiguous_module`: more than one local candidate has the same basename.
- `architecture_mismatch`: the unique candidate's reported architecture differs from the importing PE.
- `incomplete_or_unknown`: the candidate export table is incomplete or the evidence is insufficient.

## Important limits

This is a local static cross-reference, not Windows loader emulation. It does not search Windows system directories, API-set contracts, PATH, registry search paths, transitive dependencies, or runtime-loaded modules. Delay-load module names are checked against the local inventory, but delay-load symbols are not parsed. It does not follow forwarder chains. Exact name/ordinal matches do not validate ABI, calling convention, structure layout, version, security properties, or runtime behavior. A missing local DLL does not mean the operating system lacks that module.

No binary is loaded or executed, and no file is modified. The report always sets `compatibility_established` and `execution_performed` to false.
