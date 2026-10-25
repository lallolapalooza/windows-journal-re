"""Windows Journal ``NB`` container: a TIFF derivative.

Layout (Windows Journal 6.1/10.0):

    +0  char[2]  signature: "NB" (notebook), "EP" (editable paper), "II"/"MM"
    +2  u16      42 (TIFF magic)
    +4  u32      offset of the first IFD
    +8  u32      0x10000150 (writer version)
    ...          pre-IFD payload (tag values that live before the first IFD)

IFDs are standard TIFF IFDs.  Private tags used by Journal:

    0x011A XResolution (repurposed)
    0x011B YResolution (repurposed)
    0x0140 6 SHORTs (repurposed; three 0xFF000000 ARGB values)
    0x9330 UNDEFINED  raw CFB "editable paper" page (image layers)
    0x9332 UNDEFINED  zlib-wrapped UTF-16 XML, recognition text (NBRecoText)
    0x9333 UNDEFINED  zlib-wrapped CFB holding the page "InkStream"
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

from .cfb import CFB

TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}

SIG_NB = b"NB"
SIG_EP = b"EP"
SIG_II = b"II"
SIG_MM = b"MM"

TAG_IMAGE_WIDTH = 0x0100
TAG_IMAGE_HEIGHT = 0x0101
TAG_COMPRESSION = 0x0103
TAG_XRES = 0x011A
TAG_YRES = 0x011B
TAG_RES_UNIT = 0x0128
TAG_JOURNAL_A = 0x0140
TAG_EP_PAGE = 0x9330
TAG_RECO_TEXT = 0x9332
TAG_INK_STREAM = 0x9333


class NBError(ValueError):
    pass


@dataclass
class IFDEntry:
    tag: int
    type: int
    count: int
    value: int
    raw: bytes

    def as_u32(self) -> int:
        if self.type == 3 and self.count == 1:
            return struct.unpack_from("<H", self.raw, 0)[0]
        if self.type in (4, 9):
            return struct.unpack_from("<I", self.raw, 0)[0]
        raise NBError("tag %#x is not a scalar" % self.tag)

    def as_rational(self) -> tuple[int, int]:
        return struct.unpack_from("<II", self.raw, 0)

    def as_shorts(self) -> tuple[int, ...]:
        return struct.unpack("<%dH" % self.count, self.raw)


@dataclass
class IFD:
    offset: int
    entries: dict[int, IFDEntry] = field(default_factory=dict)
    next_offset: int = 0


@dataclass
class CompressedBlob:
    """The 20-byte wrapper used for tags 0x9332/0x9333."""

    kind: int
    size: int
    reserved: int
    sentinel: int
    zero: int
    payload: bytes

    @classmethod
    def parse(cls, data: bytes) -> "CompressedBlob":
        if len(data) < 0x14:
            raise NBError("compressed blob too short")
        kind, size, reserved, sentinel, zero = struct.unpack_from("<5I", data, 0)
        return cls(kind, size, reserved, sentinel, zero, zlib.decompress(data[0x14:]))

    @property
    def text(self) -> str | None:
        for enc in ("utf-16-le", "utf-8"):
            try:
                s = self.payload.decode(enc)
            except UnicodeDecodeError:
                continue
            if "<" in s:
                return s
        return None


class NBDocument:
    def __init__(self, data: bytes):
        self.data = data
        if len(data) < 12:
            raise NBError("file too short")
        self.signature = data[0:2]
        if self.signature not in (SIG_NB, SIG_EP, SIG_II, SIG_MM):
            raise NBError("bad signature %r" % self.signature)
        self.tiff_magic, self.first_ifd = struct.unpack_from("<HI", data, 2)
        if self.tiff_magic != 42:
            raise NBError("bad TIFF magic %#x" % self.tiff_magic)
        self.version = struct.unpack_from("<I", data, 8)[0] if len(data) >= 12 else 0
        self.ifds: list[IFD] = []
        self._read_ifds()

    def _read_ifds(self) -> None:
        off = self.first_ifd
        seen = set()
        while off and off not in seen:
            seen.add(off)
            if off + 2 > len(self.data):
                raise NBError("IFD offset out of range")
            n = struct.unpack_from("<H", self.data, off)[0]
            if off + 2 + 12 * n + 4 > len(self.data):
                raise NBError("truncated IFD")
            ifd = IFD(off)
            for i in range(n):
                p = off + 2 + 12 * i
                tag, typ, count = struct.unpack_from("<HHI", self.data, p)
                size = TYPE_SIZES.get(typ, 1) * count
                if size <= 4:
                    raw = self.data[p + 8:p + 8 + size]
                else:
                    voff = struct.unpack_from("<I", self.data, p + 8)[0]
                    raw = self.data[voff:voff + size]
                ifd.entries[tag] = IFDEntry(tag, typ, count,
                                            struct.unpack_from("<I", self.data, p + 8)[0], raw)
            ifd.next_offset = struct.unpack_from("<I", self.data, off + 2 + 12 * n)[0]
            self.ifds.append(ifd)
            off = ifd.next_offset

    @property
    def page_count(self) -> int:
        return len(self.ifds)

    def tag(self, ifd_index: int, tag: int) -> IFDEntry | None:
        return self.ifds[ifd_index].entries.get(tag)

    # -- Journal payloads ---------------------------------------------
    def ep_page(self, ifd_index: int = 0) -> bytes | None:
        e = self.tag(ifd_index, TAG_EP_PAGE)
        return e.raw if e else None

    def ink_stream(self, ifd_index: int = 0) -> bytes | None:
        e = self.tag(ifd_index, TAG_INK_STREAM)
        return CompressedBlob.parse(e.raw).payload if e else None

    def recognition_xml(self, ifd_index: int = 0) -> str | None:
        e = self.tag(ifd_index, TAG_RECO_TEXT)
        return CompressedBlob.parse(e.raw).text if e else None

    def ep_storage(self, ifd_index: int = 0) -> CFB | None:
        raw = self.ep_page(ifd_index)
        return CFB.parse(raw) if raw else None
