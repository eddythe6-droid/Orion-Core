# Compatibility assessment engine

Orion-Core can now turn its curated evidence catalogue into a target-specific,
machine-readable assessment.

## Commands

```powershell
python -m orion_core --assess-target windows_pc
python -m orion_core --assess-target xbox
python -m orion_core --assess-target windows_pc --subsystem graphics
python -m orion_core --capabilities-json --subsystem networking
```

## Status meanings

- `compatible`: a confirmed, non-low-confidence platform contract is documented for the target.
- `adaptable`: a confirmed extension or platform-specific variation is documented; adaptation is expected.
- `platform_specific`: the documented capability is explicitly not documented for the selected target.
- `unknown`: evidence is missing, unconfirmed, low-confidence, or does not establish support for the target.

Every assessment carries the originating claim ID, source URL, source title,
confidence, and caveats. The output explicitly states that it covers
`documented_platform_contracts_only` and that hardware validation has not
been performed.

## Important limitation

These labels assess public platform contracts, not a particular game's source
code, binary, assets, or runtime behavior. For example, a shared API contract
does not prove that a title uses it correctly on both platforms. A
`compatible` result is not a promise of a successful port, and
`platform_specific` means "not documented for this target in this evidence
record", not that no alternative implementation exists.
