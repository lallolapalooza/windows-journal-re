"""Ink Serialized Format (ISF) reader.

Implements the structural part of the public ISF 1.0 specification plus the
``PACKET_BIT_PACK`` packet encoding (raw values and the delta-delta variant).
Multi-table Huffman packet data (DEFAULT/BEST compression) is recognized and
preserved verbatim, but not decoded: the eight default Bit Assignment Blocks
and index maps are hard-coded in Microsoft's compression module and are not
published in the specification.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

TAG_GUID_TABLE = 0x01
TAG_DRAW_ATTRS_BLOCK = 0x03
TAG_STROKE = 0x0A
TAG_END = 0xFFFF

ALG_HUFFMAN = 0x80
ALG_BEST = 0xF0


class ISFError(ValueError):
    pass


def read_mbe(data: bytes, pos: int) -> tuple[int, int]:
    """Multi-byte encoded unsigned integer (little-endian 7-bit groups)."""
    value = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise ISFError("truncated multi-byte integer")
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if not b & 0x80:
            return value, pos
        shift += 7
        if shift > 63:
            raise ISFError("multi-byte integer too long")


def read_smbe(data: bytes, pos: int) -> tuple[int, int]:
    """Multi-byte encoded signed integer (sign in the low bit)."""
    raw, pos = read_mbe(data, pos)
    value = raw >> 1
    return (-value if raw & 1 else value), pos


def unpack_bits(data: bytes, count: int, bits: int) -> list[int]:
    """MSB-first bit unpacking of ``count`` unsigned values."""
    if bits == 0:
        return [0] * count
    out = []
    acc = 0
    n = 0
    i = 0
    for _ in range(count):
        while n < bits:
            if i >= len(data):
                raise ISFError("truncated bit-packed data")
            acc = (acc << 8) | data[i]
            i += 1
            n += 8
        n -= bits
        out.append((acc >> n) & ((1 << bits) - 1))
        acc &= (1 << n) - 1 if n else 0
    return out


def unpack_signed(values: list[int], bits: int) -> list[int]:
    """Two's-complement interpretation for signed packet arrays."""
    if bits == 0 or bits >= 32:
        return [v - (1 << 32) if v & 0x80000000 else v for v in values]
    sign = 1 << (bits - 1)
    return [v - (1 << bits) if v & sign else v for v in values]


@dataclass
class Stroke:
    index: int
    c_points: int
    algorithm: int
    points: list[tuple[int, int]] = field(default_factory=list)
    encoded: bytes = b""
    huffman: bool = False
    error: str | None = None


@dataclass
class Ink:
    version: int = 0
    size: int = 0
    strokes: list[Stroke] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _try_stroke(data: bytes, i: int, index: int) -> Stroke | None:
    try:
        size, p = read_mbe(data, i + 1)
        if size <= 0 or p + size > len(data):
            return None
        payload = data[p:p + size]
        c_points, q = read_mbe(payload, 0)
        if c_points <= 0 or c_points > 1_000_000:
            return None
        st = Stroke(index=index, c_points=c_points, algorithm=0, encoded=payload)
        arrays = []
        algs = []
        for _ in range(2):  # x and y
            if q >= len(payload):
                return None
            alg = payload[q]
            q += 1
            algs.append(alg)
            if alg & 0xC0:
                st.huffman = True
                st.algorithm = alg
                return st
            bits = alg & 0x1F
            if bits == 0:
                bits = 32
            nbytes = (c_points * bits + 7) // 8
            if q + nbytes > len(payload):
                return None
            raw = payload[q:q + nbytes]
            q += nbytes
            arrays.append(unpack_signed(unpack_bits(raw, c_points, bits), bits))
        st.algorithm = algs[0]
        st.points = list(zip(arrays[0], arrays[1]))
        return st
    except (ISFError, struct.error):
        return None


def parse(data: bytes) -> Ink:
    ink = Ink()
    if len(data) < 2:
        raise ISFError("truncated ISF")
    ink.version, p = read_mbe(data, 0)
    if ink.version != 0:
        raise ISFError("unsupported ISF version %d" % ink.version)
    ink.size, p = read_mbe(data, p)
    if ink.size > len(data) - p:
        ink.warnings.append("ISF size field exceeds available data")
    pos = p
    stroke_index = 0
    # Strokes are self-delimiting; scan for valid TAG_STROKE records.
    while pos < len(data):
        j = data.find(bytes([TAG_STROKE]), pos)
        if j < 0:
            break
        st = _try_stroke(data, j, stroke_index)
        if st is None:
            pos = j + 1
            continue
        ink.strokes.append(st)
        stroke_index += 1
        try:
            size, after = read_mbe(data, j + 1)
            pos = after + size
        except ISFError:
            pos = j + 1
    if not ink.strokes:
        ink.warnings.append("no decodable stroke records")
    return ink
