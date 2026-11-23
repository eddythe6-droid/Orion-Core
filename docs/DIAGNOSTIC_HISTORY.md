# Diagnostic history

Orion-Core can persist completed diagnostic snapshots as immutable JSON records.

- Default location: `%LOCALAPPDATA%\\Orion-Core\\history` on Windows, otherwise `$XDG_DATA_HOME/orion-core/history` or `~/.local/share/orion-core/history`.
- Tests and embedding applications can inject an explicit directory.
- Each record contains a schema version, stable ID, UTC timestamp, report kind, and the original report.
- Writes use a temporary file, flush/fsync, and atomic replacement.
- Records are not automatically pruned or overwritten.
- A malformed record causes an explicit error; it is never silently discarded.

This module stores snapshots only. It does not create hardware measurements, infer Xbox compatibility, or compare unrelated report kinds. The GUI and CLI integration are separate follow-up steps.
