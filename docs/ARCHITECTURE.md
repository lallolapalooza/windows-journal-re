# Architecture and evidence map

## Objective

Produce an evidence-backed description of the Windows Journal `.jnt`/`.jtp`
container and content model, sufficient for another implementation, and a
working reader that matches the shipped reader's XML byte-for-byte. If a
faithful reimplementation of any layer is not possible from the available
artifacts, that layer is documented and the limitation is stated.

## Artifacts

Source image: `Microsoft Windows 7 Ultimate with Service Pack 1 (64-bit).iso`
(archive.org item `microsoft-windows-7-ultimate-with-service-pack-1-64-bit`),
MD5 `88bacec0dab38dfdf84218924711ec8c`.

Extracted from `sources/install.wim` (component store):

| Path in image | Size | MD5 | Role |
|---|---|---|---|
| `...\TabletPC-Journal...\Journal.exe` | 2,164,224 | `1c09858449980d64577e377eb262c9d7` | application (x64, 6.1.7601.17514) |
| `...\TabletPC-Journal...\NBDoc.DLL` | 1,732,096 | `5f2b31cd314c1dcc24b5c18611bdfb28` | notebook document/page/stationery/rich-ink model |
| `...\TabletPC-Journal...\InkSeg.dll` | 929,792 | `8dde0dd93a82e7f0161137b5b39bf976` | rich-ink segment tree, XML (de)serializer |
| `...\TabletPC-Journal...\JNTFiltr.dll` | 1,393,664 | `b933cbb0ea42c219c5b82929d1ab153b` | Windows Search filter (TIFF/OCR path) |
| `...\JournalNoteWriter...\JNWDRV.dll` | 1,402,880 | `3e248d73cea054edd9a61d96c6944b01` | print-to-journal driver |
| `Program Files\Common Files\Microsoft Shared\ink\journal.dll` | 1,367,552 | `c0a81c0b58dd7074b230c5801c3312e4` | editable-paper TIFF engine **and** `IJournalReader` |
| `...\TabletPC-Journal...\Journal.jnt` | 4,544 | `5b944604be1cc246c826a7f4bd59f4e1` | official sample note |
| `...\TabletPC-Journal...\*.jtp` | 11 files | — | official templates |

The same `Journal.jnt` and templates are shipped in the Windows 10 Journal MSI
(`Journal_en-us_x86.msi`, 10.0.173), byte-identical for `Journal.jnt`.

Toolchain: Ghidra 12.2 PUBLIC, JDK 25; PE inventory and tests in Python 3.14.

## Module map (implementation)

```
src/jntread/
  cfb.py        MS-CFB reader (FAT/DIFAT/mini stream)
  cfbwrite.py   MS-CFB writer (used by synthetic tests)
  nbtiff.py     NB/TIFF container: header, IFDs, private tags, blob wrappers
  nbwrite.py    NB container writer
  propset.py    OLE property set streams
  stationery.py 0x3002 stationery record
  inkstream.py  page InkStream tag stream
  richink.py    RichInk XML -> element tree
  isf.py        ISF structural parser + PACKET_BIT_PACK decoder
  document.py   document/page model, editable-paper properties
  xmlexport.py  Journal Reader XML (reference-compatible)
  cli.py        command line
```

Data flow:

```
bytes -> nb (IFDs)
      -> tag 9330 -> CFB -> property set 2FA1FA6A -> stationery/page size
      -> tag 9333 -> zlib -> CFB -> InkStream -> tags
                                              -> 0x3002 stationery
                                              -> 0x7000 date/title
                                              -> 0x2001 RichInk XML -> nodes -> ISF
      -> tag 9332 -> zlib -> NBRecoText XML
```

## Decompiled evidence (Win7 SP1 addresses)

Ghidra image bases: NBDoc.DLL `0x7ff4e640000`, journal.dll `0x7ff49920000`,
InkSeg.dll `0x7ff42820000`.

### NBDoc.DLL

| Address | Function | Evidence for |
|---|---|---|
| `0x7ff4e6818c4` | `CNBDocument::SaveToStream` | document save path |
| `0x7ff4e681844` | `CNBDocument::LoadFromStream` | document load path |
| `0x7ff4e68b854` | `CNBPage::Save` | InkStream record sequence |
| `0x7ff4e68bf54` | `CNBPage::SaveRecoText` | `0x9332` recognition XML |
| `0x7ff4e6a5120` | `CStationery::GetAll` | 0x4C-byte stationery layout |
| `0x7ff4e6a3758` | `CStationery::GetStyle` | style slots |
| `0x7ff4e6a39a0` | `CStationery::GetColor` | five colour slots |
| `0x7ff4e6a3b34` | `CStationery::GetInchesBetween` | spacing |
| `0x7ff4e6a3c3c` | `CStationery::GetInchesBefore` | spacing |
| `0x7ff4e6a3d60` | `CStationery::GetTitleDimensions` | title rectangle |
| `0x7ff4e6a480c` / `0x7ff4e6a4ba8` | `CStationery::SaveToStream` / `LoadFromStream` | tag `0x3002` framing |
| `0x7ff4e694050` | `CRichInkPage::CreateTextBoxUnicode` | text hosted class GUID |
| `0x7ff4e699590` | `CRichInkPage::CreatePictureInternal` | image/flag GUIDs |
| `0x7ff4e6b45f0` | `CNBTextBox::StreamOutXML` | `<Text>` content |
| `0x7ff4e6b14c4` | `CNBImage::StreamOutXML` | `<Image>` content |
| `0x7ff4e6b8fb8` | `CNBFlag::StreamOutXML` | `<Flag>` content |
| `0x7ff4e6a89d4` | `CRecognitionSave::WriteRecognitionDataToXMLStream` | `NBRecoText` schema |

### journal.dll

| Address | Function | Evidence for |
|---|---|---|
| `0x7ff4994a070` | `IJournalReader` constructor | serves as the reference oracle |
| `0x7ff49928b80` | reader vtable | `ReadFromStream` at slot 3 |
| `0x7ff4994aa54` | reader main | document/page XML assembly |
| `0x7ff4994bc08` | InkStream parser | tag table §4 |
| `0x7ff4995037c` | stationery parser | §3 layout |
| `0x7ff4994c9a4` | string record parser | `0x7000` date/title |
| `0x7ff4994cb0c` | XML record parser | `0x2001` magic/length |
| `0x7ff4994c2f8` | JournalPage/TitleInfo writer | output schema |
| `0x7ff499504e8` | stationery XML writer | output schema |
| `0x7ff49960240` | `CEPEditablePageTiffImpl::WriteEPaperTags` | TIFF tag handling |
| `0x7ff4995f004` | `LoadIfdFromStorage` | TIFF load |
| `0x7ff499ba8e0` | `CIFD::WriteImageLayerToEncStream` | image-layer blobs |
| `0x7ff49932db8` | `RecognizeFiletype` | `NB`/`EP`/`II`/`MM` signatures |

The reader class CLSID is registered in the image registry as
`{B4124623-FC0E-47CE-BCA9-126A6104ADA1}` (`Journal.JournalReader.1`,
`%CommonProgramFiles%\Microsoft Shared\Ink\Journal.dll`). The interface IID used
by the class factory is `{26213A0B-5A6C-4472-923D-9F29EFF608B2}`.

`scripts/oracle_direct.py` loads the extracted `journal.dll`, calls the
constructor at RVA `0x2a070` with that IID, and invokes `ReadFromStream` with an
`IStream` over the input file. This is the ground truth used in tests.

### InkSeg.dll

| Address | Function | Evidence for |
|---|---|---|
| `0x7ff42884608` | `CGroupNode::StreamOutXML` | GroupNode serialization |
| `0x7ff4288ea88` | `CNode::StreamOutXML` | BoundingRect, ScalarTransform |
| `0x7ff4287c0e0` | `CInkNode::StreamOutXML` | InkObject, alternates, class, confidence, pinned |
| `0x7ff42891250` | `CDrawing::StreamOutXML` | Drawing |
| `0x7ff42890394` | `CWord::StreamOutXML` | InkWord |
| `0x7ff4288aa14` | `CHostedNode::StreamOutXML` | Guid/HostedBoundingRect/HostedContent |
| `0x7ff42884480` | `CGroupNode::PrepareToStreamInXML` | loader vtable |
| `0x7ff4282c678` / `0x7ff4282c748` | `StreamOutISF` / `StreamInISF` | ink objects are ISF |

The RichInk element vocabulary is in the UTF-16 string block at file offsets
`0x8c40..0x8f00` (`GroupNode`, `InkWord`, `Paragraph`, `Drawing`, `Reflow`,
`HostedNode`, `BoundingRect`, `ScalarTransform`, `Mat1..9`, `Guid`,
`HostedContent`, `Content`, `InkSegment`, `SegmentWidth`, ...).

## Verification harness

1. `scripts/oracle_direct.py` reads any file through the original reader.
2. `tests/parity.py` compares `xmlexport.document_xml` against the oracle for
   every shipped `.jtp` and `Journal.jnt`.
3. `tests/corpus.py` builds synthetic documents exercising every element
   (Text, Image, Flag, InkWord, Drawing, GroupNode, Paragraph/Line, Reflow,
   alternates, transforms, title/date, stationery with lines, multi-page) and
   compares against the oracle.
4. `tests/test_reader.py` covers the container, stationery, RichInk and ISF
   decoders without requiring the proprietary DLL, plus golden XML parity
   (`tests/golden/`).

Results: 12/12 official files, 31/31 synthetic cases, 11/11 unit tests.

## Boundaries

* Huffman-compressed ISF packet arrays are preserved and flagged but not decoded
  (default BAB/index-map tables are not published; see `FORMAT.md` §8).
* `DocImage` (optional page image) is not emitted by any available official
  file; the 0x9330 layer streams that would feed it are parsed but the exact
  page-image trigger was not exercised.
* The reference component itself is documented by Microsoft as unable to read
  files created by Windows 7 or later; all validation here used Windows 7
  templates and synthetic files, which it does read.
