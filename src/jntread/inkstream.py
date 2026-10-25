"""The page ``InkStream`` record stream (inside tag 0x9333)."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .stationery import Stationery

TAG_FLAGS = 0x4000
TAG_TIME = 0x5000
TAG_SIZE = 0x1000
TAG_SIZE2 = 0x6000
TAG_STATIONERY = 0x3002
TAG_TEXT = 0x7000
TAG_XML = 0x2001
TAG_END = 0xFFFF
MAGIC = 0x12345678


@dataclass
class InkStream:
    flags: int = 0
    created: int = 0
    width: int = 0
    height: int = 0
    width2: int = 0
    height2: int = 0
    stationery: Stationery | None = None
    date_text: str = ""
    title_text: str = ""
    richink_xml: str = ""
    extra_xml: str = ""
    trailing: bytes = b""

    @classmethod
    def parse(cls, data: bytes) -> "InkStream":
        s = cls()
        i = 0
        n = len(data)

        def u16(off):
            return struct.unpack_from("<H", data, off)[0]

        def u32(off):
            return struct.unpack_from("<I", data, off)[0]

        def bstr(off):
            ln = u32(off)
            text = data[off + 4:off + 4 + max(0, ln - 2)].decode("utf-16-le", "replace")
            return text, off + 6 + max(0, ln - 2)

        while i + 2 <= n:
            tag = u16(i)
            i += 2
            if tag == TAG_END:
                break
            if tag == TAG_FLAGS:
                s.flags = u32(i); i += 4
            elif tag == TAG_TIME:
                s.created = struct.unpack_from("<Q", data, i)[0]; i += 8
            elif tag == TAG_SIZE:
                s.width, s.height = struct.unpack_from("<II", data, i); i += 8
            elif tag == TAG_SIZE2:
                s.width2, s.height2 = struct.unpack_from("<II", data, i); i += 8
            elif tag == TAG_STATIONERY:
                st = Stationery.parse(data, i - 2)
                s.stationery = st
                i += st.consumed - 2
            elif tag in (TAG_TEXT, 0x3010):
                s.date_text, i = bstr(i)
                s.title_text, i = bstr(i)
            elif tag == TAG_XML:
                version = u16(i); i += 2
                if version == 1:
                    magic = u32(i)
                    if magic != MAGIC:
                        raise ValueError("bad richink magic")
                    ln = u32(i + 4)
                    xml = data[i + 8:i + 8 + ln]
                    s.richink_xml = xml.split(b"\0")[0].decode("utf-8", "replace")
                    i += 8 + ln + 1
                    version2 = u16(i); i += 2
                    if version2 == 1:
                        magic2 = u32(i)
                        ln2 = u32(i + 4)
                        s.extra_xml = data[i + 8:i + 8 + ln2].split(b"\0")[0].decode("utf-8", "replace")
                        i += 8 + ln2 + 1
            else:
                # Unknown tag: stop to avoid misinterpretation.
                break
        s.trailing = data[i:]
        return s
