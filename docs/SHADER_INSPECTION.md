# DXBC / DXIL shader-container metadata

Game Inspector can inspect bounded on-disk files with a `.cso`, `.dxil`, `.dxbc`, or `.spv` extension only when the bytes begin with the DXBC container signature. This first parser version handles the DXBC container envelope, chunk directory, SHDR/SHEX shader-model tokens, and the DXIL program-header fields when their expected marker is present.

## Safety and interpretation

- Maximum input size: 16 MiB; maximum chunk count: 4096.
- All offsets and chunk extents are checked against the declared container size.
- No extraction, execution, decryption, or modification is performed.
- The 16-byte container hash is not verified.
- DXIL bitcode, DXBC instructions, resource reflection, input/output signatures, root signatures, pipeline state, and GPU requirements are not decoded.
- `bytecode_validated`, `checksum_verified`, and `compatibility_established` remain false.

A recognized shader stage/model is structural metadata only. It does not establish that a particular Windows driver can execute the shader or that an Xbox game can be ported.
