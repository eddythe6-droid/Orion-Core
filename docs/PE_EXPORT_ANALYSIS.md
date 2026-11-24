# PE export analysis

Orion-Core reads the PE export data directory (IMAGE_DIRECTORY_ENTRY_EXPORT) with
bounded table sizes. The report includes export ordinal, RVA, zero or more
export names, and forwarder strings when the function RVA points back into the
export-directory range.

The parser caps export function and name counts at 10,000, checks RVA-to-file
mapping, and marks incomplete or malformed export data with
`exports_truncated_or_unavailable`. An empty export list does not prove that a
module has no dynamically exposed functionality: runtime lookup, forwarded
exports, delay loading, and non-PE interfaces may matter.

The Game Inspector desktop workspace presents PE architecture, import/export
counts, Xbox-specific module-name hints, and a short export preview. The full
machine-readable report can be exported as JSON.

This is static metadata analysis only. It does not load DLLs, resolve imports
against the local machine, execute code, or establish compatibility.
