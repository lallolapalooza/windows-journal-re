"""Writer for the NB/TIFF container used by Windows Journal."""
from __future__ import annotations

import struct

TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


def build(pages: list[list[tuple[int, int, bytes]]], signature: bytes = b"NB",
          version: int = 0x10000150, preamble: bytes = b"") -> bytes:
    """Serialize pages.

    ``pages`` is a list of pages; each page is a list of
    ``(tag, tiff_type, payload_bytes)``.  ``payload_bytes`` is the raw value
    (count is derived from the type size); values longer than 4 bytes are
    stored out of line.
    """
    if len(signature) != 2:
        raise ValueError("signature must be 2 bytes")
    data_area = bytearray(preamble)
    base = 12 + len(data_area)  # offsets in the file

    # First pass: assign out-of-line payload offsets.
    ifd_offsets = []
    pos = 12
    planned = []  # per page list of (tag, type, count, inline_bytes or offset)
    for page in pages:
        entries = []
        for tag, typ, payload in page:
            size = TYPE_SIZES.get(typ, 1) * (len(payload) // TYPE_SIZES.get(typ, 1)) if typ else len(payload)
            count = len(payload) // TYPE_SIZES[typ] if typ in TYPE_SIZES else len(payload)
            if len(payload) <= 4:
                inline = payload.ljust(4, b"\0")
                entries.append((tag, typ, count, inline, None))
            else:
                entries.append((tag, typ, count, None, len(data_area)))
                data_area += payload
                if len(data_area) % 2:
                    data_area += b"\0"
        planned.append(entries)
        ifd_offsets.append(pos)  # placeholder, recomputed below
        pos += 2 + 12 * len(entries) + 4

    # Recompute: data area sits between the preamble and the first IFD.
    first_ifd = 12 + len(data_area)
    ifd_pos = first_ifd
    ifd_offsets = []
    for entries in planned:
        ifd_offsets.append(ifd_pos)
        ifd_pos += 2 + 12 * len(entries) + 4

    out = bytearray()
    out += signature + struct.pack("<HI", 42, first_ifd)
    out += struct.pack("<I", version)
    out += preamble
    out += data_area[len(preamble):]

    for i, entries in enumerate(planned):
        out += struct.pack("<H", len(entries))
        for tag, typ, count, inline, data_off in entries:
            out += struct.pack("<HHI", tag, typ, count)
            if inline is not None:
                out += inline
            else:
                out += struct.pack("<I", 12 + data_off)
        nxt = ifd_offsets[i + 1] if i + 1 < len(ifd_offsets) else 0
        out += struct.pack("<I", nxt)
    return bytes(out)
