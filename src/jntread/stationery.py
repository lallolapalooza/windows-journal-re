"""Journal stationery record (tag 0x3002) parser."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

BG_STYLES = {0: "None", 1: "Solid"}
LINE_STYLES = {0: "None", 1: "Solid", 2: "Dash", 3: "Dot", 4: "DashDot", 5: "DashDotDot", 6: "Double"}
TITLE_STYLES = {0: "None", 1: "SolidSquare", 2: "OutlineSquare", 3: "SolidRoundRect",
                4: "OutlineRoundRect", 5: "SolidRoundRectDottedBaseline"}
DATE_STYLES = {0: "None", 1: "Short"}
IMAGE_STYLES = {0: "Tile", 1: "Center", 2: "Stretch", 3: "TopLeft", 4: "TopRight"}
MARGIN_TYPES = {0: "Left", 1: "Right"}

STRUCT_SIZE = 0x4C
TAG = 0x3002


@dataclass
class Stationery:
    bg_style: int = 0
    h_style: int = 0
    v_style: int = 0
    margin_style: int = 0
    title_style: int = 0
    date_style: int = 0
    image_style: int = 0
    image_fade: int = 0
    margin_type: int = 0
    pad: int = 0
    bg_color: tuple[int, int, int] = (0, 0, 0)
    h_color: tuple[int, int, int] = (0, 0, 0)
    v_color: tuple[int, int, int] = (0, 0, 0)
    margin_color: tuple[int, int, int] = (0, 0, 0)
    title_color: tuple[int, int, int] = (0, 0, 0)
    h_between: float = 0.0
    h_before: float = 0.0
    v_between: float = 0.0
    v_before: float = 0.0
    margin_spacing: float = 0.0
    title_left: float = 0.0
    title_right: float = 0.0
    title_top: float = 0.0
    title_bottom: float = 0.0
    image_name: str = ""
    image_data: bytes = b""
    consumed: int = 0

    @classmethod
    def parse(cls, data: bytes, offset: int = 0) -> "Stationery":
        if offset + 2 > len(data) or struct.unpack_from("<H", data, offset)[0] != TAG:
            raise ValueError("stationery tag 0x3002 not found")
        p = offset + 2
        vals = struct.unpack_from("<9H", data, p)
        s = cls(bg_style=vals[0], h_style=vals[1], v_style=vals[2], margin_style=vals[3],
                title_style=vals[4], date_style=vals[5], image_style=vals[6],
                image_fade=vals[7], margin_type=vals[8])
        p += 18 + 2  # 9 uint16 + pad
        colors = struct.unpack_from("<5I", data, p)
        for attr, c in zip(("bg_color", "h_color", "v_color", "margin_color", "title_color"), colors):
            setattr(s, attr, (c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF))
        p += 20
        floats = struct.unpack_from("<9f", data, p)
        (s.h_between, s.h_before, s.v_between, s.v_before, s.margin_spacing,
         s.title_left, s.title_right, s.title_top, s.title_bottom) = floats
        p += 36
        name_len = struct.unpack_from("<I", data, p)[0]
        p += 4
        s.image_name = data[p:p + name_len].decode("utf-16-le", "replace").rstrip("\0")
        p += name_len
        image_size, reserved = struct.unpack_from("<II", data, p)
        p += 8
        s.image_data = data[p:p + image_size]
        p += image_size
        s.consumed = p - offset
        return s


def color_hex(c: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % c
