# PE dependency triage

The `dependency_analysis` module turns the PE analyzer's normal and delay-load
DLL inventories into a compact dependency triage report.

It uses three deliberately cautious labels:

- `windows_module_name_candidate`: the imported name is on a small list of
  common Windows modules. This does not prove symbol or version compatibility.
- `xbox_platform_module_hint`: the name matches a known Xbox/GDK hint. This
  does not describe the module ABI or provide a replacement.
- `unclassified_module`: no conclusion is drawn from the name.

The report preserves imported symbol names where the PE analyzer recovered
them. It does not parse DLL exports, resolve ordinal imports, inspect API-set
forwarders, resolve transitive dependencies, load a DLL, or execute the game.

## Why this is a useful next step

A raw import list is difficult to turn into engineering work. This triage
separates likely Windows-facing dependencies from platform-specific clues and
unknowns. The next research task can then focus on a small, evidence-backed
set of Xbox-specific modules and their documented contracts rather than
assuming that all imports need to be reimplemented.

This is static inventory only. It cannot establish that an Xbox executable
will start on Windows or that a port is feasible.
