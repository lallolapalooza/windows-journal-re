"""OLE property set stream parsing (MS-OLEPS subset used by Journal)."""
from __future__ import annotations

import struct
import uuid

VT_I2, VT_I4, VT_R4, VT_R8 = 2, 3, 4, 5
VT_UI2, VT_UI4 = 0x12, 0x13
VT_LPWSTR, VT_LPSTR = 0x1E, 0x1F
VT_BLOB, VT_STREAM, VT_STORAGE, VT_FILETIME = 0x41, 0x42, 0x43, 0x40

_TYPE_SIZE = {VT_I2: 2, VT_UI2: 2, VT_I4: 4, VT_UI4: 4, VT_R4: 4, VT_R8: 8}

class PropertySetError(ValueError):
    pass

def sections(data: bytes):
    if data[:2] != b"\xfe\xff":
        raise PropertySetError("not a property set stream")
    n = struct.unpack_from("<I", data, 24)[0]
    out = []
    for i in range(n):
        fmtid = data[28 + i * 20:44 + i * 20]
        off = struct.unpack_from("<I", data, 44 + i * 20)[0]
        size, count = struct.unpack_from("<II", data, off)
        out.append((uuid.UUID(bytes_le=bytes(fmtid)), off, size, count))
    return out

def properties(data: bytes, section_offset: int):
    """Yield (propid, vt, value_offset, raw_value_bytes)."""
    size, count = struct.unpack_from("<II", data, section_offset)
    for i in range(count):
        pid, poff = struct.unpack_from("<II", data, section_offset + 8 + i * 8)
        p = section_offset + poff
        vt = struct.unpack_from("<I", data, p)[0]
        yield pid, vt, p, _raw(data, vt, p)

def _raw(data: bytes, vt: int, p: int) -> bytes:
    if vt == VT_I2:
        return data[p + 4:p + 6]
    if vt == VT_UI2:
        return data[p + 4:p + 6]
    if vt in (VT_I4, VT_UI4, VT_R4):
        return data[p + 4:p + 8]
    if vt == VT_R8:
        return data[p + 4:p + 12]
    if vt in (VT_LPWSTR, VT_LPSTR, VT_BLOB, VT_STREAM, VT_STORAGE):
        ln = struct.unpack_from("<I", data, p + 4)[0]
        return data[p + 8:p + 8 + ln]
    return b""
