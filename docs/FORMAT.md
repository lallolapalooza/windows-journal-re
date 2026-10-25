# Windows Journal `.jnt` / `.jtp` format

All offsets are hexadecimal. All integers are little-endian. Lengths are bytes
unless stated. Claims are from static analysis of the Windows 7 SP1 binaries
listed in `ARCHITECTURE.md`; the "verified" column refers to the reference
reader parity harness.

## 1. Container

`.jnt` notes and `.jtp` templates share one container: a TIFF derivative whose
byte-order signature is `"NB"` instead of `"II"`.

```
+00  char[2]  signature  'N','B'          (recognizer also accepts 'EP','II','MM')
+02  u16      42                         (TIFF magic)
+04  u32      offset of the first IFD
+08  u32      0x10000150                 (writer version)
+0C  ...      pre-IFD payload            (values referenced by the IFD)
```

IFDs are standard TIFF IFDs (u16 count, 12-byte entries, u32 next-IFD offset).
Multiple pages are chained through the next-IFD pointer; each page has its own
IFD.

| Tag | Type | Content |
|---|---|---|
| `00FE,0100,0101,0102,0103,0106,0111,0115,0116,0117,0128` | std | dummy 1x1 TIFF image fields |
| `011A` | RATIONAL | 102/1 for notes, 61/1 for templates (unused by the reader) |
| `011B` | RATIONAL | 108/1 (unused by the reader) |
| `0140` | SHORT[6] | three `0xFF000000` values (unused by the reader) |
| `9330` | UNDEFINED | raw CFB: editable-paper page (property sets/layers) |
| `9332` | UNDEFINED | zlib-wrapped UTF-16 `NBRecoText` XML |
| `9333` | UNDEFINED | zlib-wrapped CFB containing the `InkStream` stream |

### Compressed blob wrapper (tags `9332`, `9333`)

```
+00 u32  type           2
+04 u32  decompressed size
+08 u32  1
+0C u32  0xFFFFFFFF
+10 u32  0
+14 ...  zlib stream
```

`9333` decompresses to a CFB with one stream named `InkStream`.
`9332` decompresses to XML (UTF-16LE with a UTF-16 NUL terminator).

## 2. Editable-paper page (tag `9330`)

A CFB with random storage names. The reader uses the storage whose property
set has FMTID

```
2FA1FA6A-0916-4D0A-A742-D42136C2D43E
```

| Prop | Type | Meaning |
|---|---|---|
| 1 | VT_I2 | 1200 (writing-unit code page) |
| `0x80000000` | VT_UI4 | locale (1033) |
| 2 | VT_BLOB | stationery record (starts with `0x3002`) |
| 3 | VT_R4 | page width in inches |
| 4 | VT_R4 | page height in inches |
| 5 | VT_UI2 | language id |
| 6 | VT_UI4 | 2 (constant in all samples) |
| 7 | VT_UI4 | 0 (constant in all samples) |

Other storages in the same CFB (`13795680-4F98-11D3-96DD-00C04F6888FF`,
`1D75D720-BE80-4368-B01F-61ADF221A84F`, `5D58C06D-3094-412C-BDCC-8A201A3A2BDC`,
`SummaryInformation`) carry image-layer and stream descriptors. Mutating them
does not change the Journal Reader output; they are preserved but not required
for the element model.

## 3. Stationery record (`0x3002`)

Written by `CStationery::SaveToStream`/`GetAll` (NBDoc.DLL). The struct starts
immediately after the 2-byte tag and is 0x4C bytes, followed by the optional
background image.

| Offset | Type | Field |
|---|---|---|
| 02 | u16 | background style: 0=None, 1=Solid |
| 04 | u16 | horizontal-line style |
| 06 | u16 | vertical-line style |
| 08 | u16 | margin-line style |
| 0A | u16 | title style: 0=None,1=SolidSquare,2=OutlineSquare,3=SolidRoundRect,4=OutlineRoundRect,5=SolidRoundRectDottedBaseline |
| 0C | u16 | date style: 0=None, 1=Short |
| 0E | u16 | background-image style: 0=Tile,1=Center,2=Stretch,3=TopLeft,4=TopRight |
| 10 | u16 | background-image fade (0..255) |
| 12 | u16 | margin type: 0=Left, 1=Right |
| 14 | u16 | pad |
| 16 | 4×u8 | background colour R,G,B,A |
| 1A | 4×u8 | horizontal-line colour |
| 1E | 4×u8 | vertical-line colour |
| 22 | 4×u8 | margin-line colour |
| 26 | 4×u8 | title colour |
| 2A | f32 | horizontal spacing between |
| 2E | f32 | horizontal spacing before |
| 32 | f32 | vertical spacing between |
| 36 | f32 | vertical spacing before |
| 3A | f32 | margin spacing |
| 3E | f32 | title left (inches) |
| 42 | f32 | title right (inches) |
| 46 | f32 | title top (inches) |
| 4A | f32 | title bottom (inches) |
| 4E | u32 | image-name length (bytes, includes UTF-16 NUL) |
| 52 | UTF-16 | image name |
| .. | u32,u32 | image data size, 0 |
| .. | bytes | image data (EMF for all shipped templates) |

The reference reader converts inches to 1/100 mm by multiplying by 2540 and
rounding each edge; width/height are the differences of the rounded edges.

## 4. `InkStream` records (inside tag `9333`)

Sequential `tag(u16) + payload` records, written by `CNBPage::Save`
(NBDoc.DLL) and parsed by `FUN_7ff4994bc08` (journal.dll).

| Tag | Payload |
|---|---|
| `0x4000` | u32 flags (2 for notes, 0 for templates) |
| `0x5000` | u64 FILETIME |
| `0x1000` | u32 width, u32 height in 1/1000 inch |
| `0x6000` | u32 alternate width, u32 alternate height (only when sizes differ) |
| `0x3002` | stationery record (§3) |
| `0x7000` | two length-prefixed strings: date then title. Each: u32 byte length (including a 2-byte NUL), UTF-16LE text, NUL |
| `0x3010` | alias for `0x7000` |
| `0x2001` | u16 version (1); u32 magic `0x12345678`; u32 XML length; XML bytes + NUL; u16 second-document flag (0/1); optional second XML in the same framing |
| `0xFFFF` | end |

Unknown tag: parsing stops (the reference reader does the same).

## 5. RichInk XML (`0x2001`)

Namespace `urn:schemas-microsoft-com:tabletpc:richink`.
The first document is the card's rich-ink segment; the optional second document
is only parsed into the page model and not surfaced by the reference XML.

```
<InkSegment>
  <Version>1</Version>
  <SegmentWidth>7760</SegmentWidth>          host units = 1/1000 inch
  <SegmentHeight>9458</SegmentHeight>
  <SegmentLineHeight>460</SegmentLineHeight>
  <EmusPerHostUnit>914.4</EmusPerHostUnit>   (1 host unit = 914.4 EMU)
  <LanguageID>1033</LanguageID>
  <Content>...</Content>
</InkSegment>
```

Content nodes (all children direct; no wrapper except the top-level `Content`):

| Element | Children / attributes |
|---|---|
| `GroupNode` | `BoundingRect X= Y= Width= Height=` (host units), optional `ScalarTransform Mat1..Mat9`, then child nodes |
| `Reflow` | child nodes |
| `Paragraph BlockNumber=` | `Line LineNumber=` |
| `Line` | `InkWord` nodes, then `ParagraphLineMetrics` |
| `InkWord` | `BoundingRect`, optional `ScalarTransform`, `AlternateList/Alternate`, `CanReclassify`, `InkClass`, `Confidence`, `Pinned`, `InkObject` |
| `Drawing` | same as `InkWord` |
| `HostedNode` | `BoundingRect`, `Guid`, `HostedBoundingRect`, `HostedContent` |
| `InkObject` | `base64:` prefix followed by ISF bytes (base64) |
| `ParagraphLineMetrics` | `Baseline PointA="x,y" PointB="x,y"`, optional `Ascender/Descender/Midline` |
| `HostedContent` | `Text` (UTF-8 text) or `Image` (`base64:` + bytes) |

Hosted-node class GUIDs (from `CRichInkPage::CreateTextBoxUnicode`,
`CreatePictureInternal`):

| GUID | Journal Reader element |
|---|---|
| `{29C4CC4F-5A37-4D53-9FE4-F74731B2D444}` | `Text` |
| `{A201ECB0-0C0A-4C81-84E4-D82614E2ACBA}` | `Image` |
| `{EBD73B02-79E6-4899-B70C-DD185CF4E26B}` | `Flag` |

## 6. Titles

`0x7000` supplies the date and title strings. The date is a locale-formatted
string (the reference reader parses it as an OLE date; e.g.
`1/2/2020 3:04:05 AM` or `02.01.2020 03:04:05`). Empty means
`0000-00-00T00:00:00` in the output.

## 7. Recognition XML (tag `9332`)

`NBRecoText`, UTF-16LE with a UTF-16 NUL terminator:

```xml
<?xml version="1.0?">
<NBRecoText>
    <version>1.0</version>
    <flag>nil</flag>
    <numWords>0</numWords>
    <localeID>1033</localeID>
</NBRecoText>
```

Word/tag records are appended by `CRecognitionSave::WriteRecognitionDataToXMLStream`
when recognition data exists; the templates carry only the header.

## 8. Ink Serialized Format (ISF)

`InkObject` is ISF 1.0 (Microsoft's public specification). The reader implements
the structural stream and `PACKET_BIT_PACK` packet arrays:

* algorithm byte `0x00..0x7F`: `cBits = alg & 0x1F` (`0` means 32), values are
  bit-packed MSB-first, two's complement; bit `0x40` selects the
  delta-delta transform instead of raw values.
* `0x80..0xBF` / `0xF0..`: multi-table Huffman ("DEFAULT"/"BEST" compression).

Validated identifiers: `TAG_GUID_TABLE=0x01`, `TAG_DRAW_ATTRS_BLOCK=0x03`,
`TAG_STROKE=0x0A`; predefined property GUID indices start at 50
(`GUID_COLORREF=68`, `GUID_PEN_WIDTH=69`, `GUID_DRAWING_FLAGS=72`).

**Limitation:** the eight default Huffman Bit Assignment Blocks and index maps
are hard-coded in Microsoft's compression module and are not published in the
ISF specification. Huffman-compressed arrays are therefore preserved verbatim
and flagged (`huffman: true`), not decoded. Uncompressed/bit-packed arrays are
decoded to points.

## 9. Reference-reader conversion rules

| Output | Rule |
|---|---|
| `DefaultPageWidth/Height` | `round(props[3/4] * 2540)` from the first page's editable-paper property set |
| page `Width`/`Height` | `floor(SegmentWidth/Height * 2.54)` |
| `LineHeight` | `floor(SegmentLineHeight * 2.54)` |
| `LanguageId` | `LanguageID` from the RichInk XML |
| bounds | `round(host * 2.54)` |
| colours | stored as R,G,B,A bytes; output `#rrggbb` |
| spacing | `round(inches * 2540)` |
| stationery selection | document-level stationery from the first page's `9330` property set; page-level stationery only when `InkStream` has a `0x3002` record |
| content | omitted entirely when the page has no RichInk XML |
