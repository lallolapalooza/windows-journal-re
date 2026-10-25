# Windows Journal `.jnt` / `.jtp` — format RE + reader

Static reverse engineering of the Windows Journal container shipped in
**Windows 7 Ultimate SP1 x64**, plus a self-contained Python reader that
reproduces the shipped `IJournalReader` XML byte-for-byte on the official
Microsoft templates and on a synthetic corpus covering every element type.

* Format specification: [`docs/FORMAT.md`](docs/FORMAT.md)
* Architecture and decompiled evidence map: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
* Session archive (full analysis transcript, OMP format): [`archive/`](archive/README.md)

## What was recovered

```
NB container (TIFF derivative, signature "NB")
├─ IFD per page
├─ tag 0x9330  raw CFB  editable-paper page: property sets, stationery, image layers
├─ tag 0x9332  zlib → XML   recognition text (NBRecoText)
└─ tag 0x9333  zlib → CFB   page "InkStream" record stream
     ├─ 0x4000 flags, 0x5000 timestamp, 0x1000 page size
     ├─ 0x3002 stationery record (styles, colours, spacing, title rect, EMF background)
     ├─ 0x7000 date + title strings
     └─ 0x2001 RichInk XML (GroupNode, Paragraph/Line, InkWord, Drawing, Reflow,
                            HostedNode → Text/Image/Flag, ISF InkObject)
```

The dossier documents every tag, offset, table and conversion rule, including
the reference reader's rounding (`round(v*2.54)` for bounds, `floor(v*2.54)` for
page size, `round(inches*2540)` for stationery geometry) and the three hosted
class GUIDs used by Text/Image/Flag.

## Reader

Pure standard library, Python 3.10+.

```bash
PYTHONPATH=src python -m jntread file.jnt            # summary
PYTHONPATH=src python -m jntread file.jnt --xml      # Journal Reader XML
PYTHONPATH=src python -m jntread file.jtp --json     # full model, incl. stroke points
```

The package parses:

* CFB (FAT/DIFAT/mini stream) and the NB/TIFF container
* OLE property sets and the editable-paper page properties
* the stationery record (all styles, colours, spacing and background images)
* the `InkStream` tags, title/date and recognition XML
* the RichInk content tree, including hosted text/image/flag nodes
* ISF `InkObject`s: structural stream + bit-packed stroke geometry

### Verification

| Check | Result |
|---|---|
| Official Microsoft files (11 `.jtp` + `Journal.jnt`) vs. the shipped reader | **12/12 byte-identical XML** |
| Synthetic corpus (every element, title/date, line stationery, multi-page) | **31/31 byte-identical XML** |
| Unit tests | **11/11** |

Ground truth is the original Win7 `journal.dll` reader
(`CLSID {B4124623-FC0E-47CE-BCA9-126A6104ADA1}`) invoked by
[`scripts/oracle_direct.py`](scripts/oracle_direct.py). See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full harness.

### Known limitation

Huffman-compressed ISF packet arrays are preserved verbatim and flagged
(`huffman: true`) but not decoded. The eight default Bit Assignment Blocks and
index maps used by Microsoft's compression module are not published in the ISF
specification. Bit-packed arrays are fully decoded to points.

## Reproducing the analysis

The repository does **not** redistribute Microsoft binaries, the ISO, or the
Microsoft `.jtp`/`.jnt` samples. You need your own copy of the
[Windows 7 Ultimate SP1 x64 image](https://archive.org/details/microsoft-windows-7-ultimate-with-service-pack-1-64-bit)
(MD5 `88bacec0dab38dfdf84218924711ec8c`).

1. Extract `install.wim` and then:
   * `Windows/winsxs/...TabletPC-Journal.../Journal.exe`, `NBDoc.DLL`, `InkSeg.dll`, `*.jtp`, `Journal.jnt`
   * `Program Files/Common Files/Microsoft Shared/ink/journal.dll`
2. Put the binaries in `extracted/win7/files/` and the samples in `samples/`
   (paths used by the tooling; see `scripts/`).
3. Run the reference oracle and the parity suites:

```bash
python scripts/oracle_direct.py samples/blank.jtp
python tests/parity.py
python tests/corpus.py
```

Ghidra tooling used for the analysis is in `scripts/ghidra-scripts/`
(`DecompileByNameFile.java`, `RefsForStrings.java`, `DumpMem.java`, ...).

## Repository layout

```
src/jntread/       reader package (stdlib only)
docs/              format specification + evidence map
scripts/           reference oracle, mutation probe, Ghidra helpers
tests/             unit tests, parity harness, synthetic corpus
archive/           omp session archive of the analysis
```

## Provenance

Windows 7 Ultimate SP1 x64 ISO: MD5 `88bacec0dab38dfdf84218924711ec8c`,
3,319,496,704 bytes.

| Artifact | MD5 |
|---|---|
| `Journal.exe` 6.1.7601.17514 x64 | `1c09858449980d64577e377eb262c9d7` |
| `journal.dll` (IJournalReader) | `c0a81c0b58dd7074b230c5801c3312e4` |
| `NBDoc.DLL` | `5f2b31cd314c1dcc24b5c18611bdfb28` |
| `InkSeg.dll` | `8dde0dd93a82e7f0161137b5b39bf976` |
| `JNTFiltr.dll` | `b933cbb0ea42c219c5b82929d1ab153b` |
| `JNWDRV.dll` | `3e248d73cea054edd9a61d96c6944b01` |
| `Journal.jnt` | `5b944604be1cc246c826a7f4bd59f4e1` |

No Microsoft binaries or assets are redistributed. The ISF layer is implemented
from Microsoft's public *Ink Serialized Format Specification*.

## License

MIT — see [`LICENSE`](LICENSE). Windows and Windows Journal are trademarks of
Microsoft Corporation; this project is unaffiliated.
