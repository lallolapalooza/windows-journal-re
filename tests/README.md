# Tests

Self-contained tests (no Microsoft files needed):

```bash
python -m unittest discover -s tests
```

`test_reader.py` covers the CFB writer/reader, the NB container, the stationery
record, the InkStream tags, the RichInk tree, ISF bit-pack decoding, and a full
synthetic document -> Journal Reader XML conversion.

## Parity against the shipped reader

`parity.py` and `corpus.py` require:

* the extracted Windows 7 SP1 binaries in `extracted/win7/files/`
  (`journal.dll`, `NBDoc.DLL`, `InkSeg.dll`, ...);
* the official samples in `samples/` (`blank.jtp`, `Journal.jnt`, ...).

Both scripts exit with a skip message when the samples are absent.

```bash
python scripts/oracle_direct.py samples/blank.jtp   # reference XML
python tests/parity.py                              # official files
python tests/corpus.py                              # synthetic corpus
```
