# DXBC / DXIL shader-container metadata

Game Inspector can inspect bounded on-disk files with a `.cso`, `.dxil`, `.dxbc`, or `.spv` extension when the bytes begin with a recognized DXBC container signature or SPIR-V module magic. The inspector identifies shader binaries by magic rather than trusting their filename. It handles the DXBC container envelope, chunk directory, SHDR/SHEX shader-model tokens, common RDEF resource-binding records, and the DXIL program-header fields when their expected marker is present. It also recognizes the fixed five-word SPIR-V module header (version, generator, ID bound, and schema), including byte-swapped modules. A bounded instruction walk inventories opcode counts and selected `OpCapability`, `OpExtension`, and `OpEntryPoint` operands.

## Safety and interpretation

- Maximum input size: 16 MiB; maximum DXBC chunk count: 4096.
- Supported signatures: DXBC container and SPIR-V module magic. `.cso`, `.dxbc`, `.dxil`, and `.spv` extensions are hints only; detected binary format is determined from bytes.
- A filename/format mismatch is reported rather than silently reclassifying the content.
- All offsets and chunk extents are checked against the declared container size.
- No extraction, execution, decryption, or modification is performed.
- The 16-byte container hash is not verified.
- RDEF parsing is limited to the common 28-byte header and 32-byte resource-binding records. Constant-buffer layouts and version-specific variants are not decoded.
- DXIL bitcode, DXBC instructions, input/output signatures, root signatures, pipeline state, and GPU requirements are not decoded.
- SPIR-V instruction framing is checked for word alignment, non-zero word counts, and in-module bounds. Only opcode counts plus `OpCapability`, `OpExtension`, and `OpEntryPoint` metadata are inventoried; this is not semantic SPIR-V validation.
- SPIR-V IDs, types, control flow, decorations, descriptor layouts, execution modes, and capability requirements are not resolved.
- `bytecode_validated`, `checksum_verified`, and `compatibility_established` remain false.

A recognized shader stage/model is structural metadata only. It does not establish that a particular Windows driver can execute the shader or that an Xbox game can be ported.
