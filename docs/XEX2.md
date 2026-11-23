# Xbox 360 XEX2 metadata inspection

Orion-Core's XEX2 parser reads the public wrapper header and selected metadata only.

## Parsed fields

- Fixed 0x18-byte big-endian header: module flags, PE-data offset, security-info offset and optional-header count.
- Bounded optional-header directory (key/value pairs).
- Inline entry point, image base and original base fields when present.
- Fixed-size execution-info optional header: Media ID, version words, Title ID, platform, executable type, disc number/count and save-game ID.
- Module flag indicators.

The parser caps the optional-header count and reads at most a 16 MiB prefix. Optional-header offsets outside the available prefix are not followed. Unknown optional headers are preserved as raw key/value pairs.

## Not parsed

XEX2 wraps a PowerPC PE image. The PE payload may be encrypted and/or compressed. Orion-Core does not decrypt, decompress, extract or execute that payload. It also does not verify RSA signatures, parse security-page hash descriptors, resolve kernel import ordinals, or infer game compatibility from metadata.

The optional-header key encodings differ: some values are inline, some point to fixed-size structures, and keys ending in 0xFF point to size-prefixed structures. The current parser decodes only the verified fields listed above; all other entries remain raw metadata.

## Research references

- [XEX2 format overview](https://reverseengineering.wiki/index.php/Format%3AXEX2_%28Xbox_360_executable%29)
- [Xenia XEX2 structures](https://github.com/xenia-project/xenia/tree/master/src/xenia/kernel/util)
- [Xbox 360 XEX format reference](https://github.com/EthanMeep/xboxwiki/blob/master/XEX.md)

These are community reverse-engineering references, not an official Microsoft specification. Treat fields not yet cross-checked against independent implementations and lawful samples as provisional.
