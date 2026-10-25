"""Top-level Journal document model (``.jnt`` / ``.jtp``)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .cfb import CFB
from .nbtiff import NBDocument
from .inkstream import InkStream
from .richink import Segment, parse as parse_richink
from .stationery import Stationery
from . import propset

FMTID_PAGE = "2fa1fa6a-0916-4d0a-a742-d42136c2d43e"


@dataclass
class Page:
    number: int
    ep_storage: CFB | None = None
    ep_stationery: Stationery | None = None
    ep_width_inches: float = 0.0
    ep_height_inches: float = 0.0
    ep_language: int = 0
    ink: InkStream | None = None
    segment: Segment | None = None
    reco_xml: str = ""

    @property
    def stationery(self) -> Stationery | None:
        if self.ink and self.ink.stationery is not None:
            return self.ink.stationery
        return self.ep_stationery


@dataclass
class Document:
    data: bytes
    nb: NBDocument
    pages: list[Page] = field(default_factory=list)

    @classmethod
    def parse(cls, data: bytes) -> "Document":
        nb = NBDocument(data)
        doc = cls(data=data, nb=nb)
        for idx in range(nb.page_count):
            page = Page(number=idx + 1)
            try:
                ep = nb.ep_storage(idx)
            except Exception:
                ep = None
            page.ep_storage = ep
            if ep is not None:
                page.ep_stationery, page.ep_width_inches, page.ep_height_inches, page.ep_language = \
                    _ep_properties(ep)
            raw_ink = nb.ink_stream(idx)
            if raw_ink is not None:
                try:
                    cfb = CFB.parse(raw_ink)
                    stream = cfb.read_stream(next(e for path, e in cfb.iter_streams()
                                                  if path[-1] == "InkStream"))
                    page.ink = InkStream.parse(stream)
                except Exception:
                    page.ink = None
            if page.ink and page.ink.richink_xml:
                try:
                    page.segment = parse_richink(page.ink.richink_xml)
                except Exception:
                    page.segment = None
            xml = nb.recognition_xml(idx)
            if xml:
                page.reco_xml = xml
            doc.pages.append(page)
        return doc

    @property
    def default_width(self) -> int:
        if self.pages and self.pages[0].ep_width_inches:
            return round(self.pages[0].ep_width_inches * 2540)
        return 0

    @property
    def default_height(self) -> int:
        if self.pages and self.pages[0].ep_height_inches:
            return round(self.pages[0].ep_height_inches * 2540)
        return 0

    @property
    def stationery(self) -> Stationery | None:
        if not self.pages:
            return None
        return self.pages[0].ep_stationery


def _ep_properties(cfb: CFB):
    """Read the Journal page property set (FMTID 2FA1FA6A...)."""
    stationery = None
    width = height = 0.0
    language = 0
    for path, entry in cfb.iter_streams():
        if path[-1] != "CONTENTS":
            continue
        raw = cfb.read_stream(entry)
        if raw[:2] != b"\xfe\xff":
            continue
        for fmtid, off, size, count in propset.sections(raw):
            if str(fmtid) != FMTID_PAGE:
                continue
            for pid, vt, p, value in propset.properties(raw, off):
                if pid == 2 and vt == propset.VT_BLOB:
                    try:
                        stationery = Stationery.parse(value, 0)
                    except Exception:
                        stationery = None
                elif pid == 3 and vt == propset.VT_R4:
                    width = struct_unpack_f(value)
                elif pid == 4 and vt == propset.VT_R4:
                    height = struct_unpack_f(value)
                elif pid == 5 and vt == propset.VT_UI2:
                    language = int.from_bytes(value, "little")
    return stationery, width, height, language


def struct_unpack_f(b: bytes) -> float:
    import struct
    return struct.unpack("<f", b[:4])[0]
