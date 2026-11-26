# Xbox XVD / XVC metadata inspection

Orion-Core includes a bounded, read-only parser for the fixed Xbox Virtual Drive (XVD) header and the public metadata tables at the start of an Xbox Virtual Container (XVC). XVC is the Xbox console game package format; it is not the PC MSIXVC package format.

## Parsed metadata

For a file with the `msft-xvd` header magic at offset `0x200`, the parser reads the fixed `0x3000`-byte header and reports:

- format version, volume flags, content type, volume/user/product/build identifiers, sandbox ID and package-version fields;
- virtual drive size, embedded-XVD length, user-data length, XVC metadata length, dynamic-header length and block size;
- encryption and data-integrity flags as declared in the header;
- extension-entry fields and conservative file-range checks;
- a calculated metadata-layout estimate for the embedded XVD, mutable data, hash tree, user data and XVC manifest.

For recognized XVC content types, the parser uses the header's page counts and integrity flags to locate the XVC metadata block. It then parses bounded public manifest fields:

- content ID, package description and encryption-key GUID slots (including empty slots, preserving slot indexes); region key references are resolved to GUIDs only when the referenced slot is populated;
- region reserved/padding fields and unknown flag bits are preserved as raw metadata rather than silently discarded;
- region records: region ID, description, flags, key reference, first update-segment index, file offset and length;
- update-segment page numbers and stored metadata hash values;
- version-2 region key/value specifiers.

The manifest parser validates declared counts against fixed limits and each table against the declared manifest length before reading it. A malformed manifest does not erase an otherwise readable XVD header report. It also reports any declared manifest bytes left uninterpreted after the known versioned tables; these may be alignment padding or fields from an unrecognized format revision and are not automatically treated as corruption.

After parsing, Orion-Core also reports conservative cross-reference observations: duplicate or unknown region IDs, key-slot references outside the declared key count, first-segment indexes outside the segment table, region ranges outside the file, observed region-range overlaps, specifiers without a matching region, and whether the initial-play/preview region IDs match a declared region. These are diagnostics, not automatic corruption verdicts: overlapping regions or unfamiliar IDs may be legitimate in variants not represented by the public mapping.

## Explicit limits

The parser does not read or reconstruct the filesystem, extract embedded XVDs, mount containers, read region payloads, decrypt data, retrieve or derive keys, bypass licensing/DRM, verify signatures, recompute hashes, or execute files. A non-zero signature area is not proof of authenticity. Header flags are reported as metadata, not independently verified properties.

Manifest inspection is limited to 16 MiB; counts are bounded for region, update-segment, encryption-key and region-specifier tables. Region offsets are checked against the file length but payload bytes are never read. Offset calculations are reported as metadata-layout estimates and may not cover every historical or future variant.

The header and manifest layouts are based on the publicly mapped XVD/XVC structures referenced below. XVC and XVD remain different from the Xbox 360 STFS/SVOD formats and from PC MSIXVC/MSIXVC2 packaging.

## References

- [Microsoft GDK packaging overview](https://learn.microsoft.com/en-us/xbox/gdk/docs/features/common/packaging/overviews/packaging?view=gdk-2604) — distinguishes console XVC from PC MSIXVC/MSIXVC2.
- [Xbox One Research Wiki: Xbox Virtual Drive](https://github.com/xboxoneresearch/wiki/blob/master/docs/operating-system/xbox-virtual-drive.md) — public high-level description of the XVD/XVC regions and metadata.
- [emoose/xvdtool: XVD structure mapping](https://github.com/emoose/xvdtool/blob/master/LibXboxOne/XVD/XVDStructs.cs) — public field mapping used as a cross-reference for the read-only metadata layout.

No Microsoft package signature, title identity, completeness or Windows compatibility is asserted by this parser.
