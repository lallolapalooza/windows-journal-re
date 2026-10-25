"""Minimal MS-CFB writer (read-compatible with Windows StgOpenStorage).

Produces a single FAT, one directory sector (more if needed), a miniFAT and a
mini stream for small streams, and regular sector chains for large streams.
Directory entries form a balanced binary tree ordered by the MS-CFB name rule.
"""
from __future__ import annotations

import struct

SECTOR = 512
MINI = 64
CUTOFF = 4096
FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
NOSTREAM = 0xFFFFFFFF


def _key(name: str) -> tuple[int, str]:
    return (len(name), name.upper())


def _entry(name: str, typ: int, start: int, size: int, left: int, right: int, child: int) -> bytes:
    b = bytearray(128)
    nm = name.encode("utf-16-le") + b"\0\0"
    b[: len(nm)] = nm
    struct.pack_into("<H", b, 0x40, len(nm))
    b[0x42] = typ
    b[0x43] = 1 if typ in (1, 5) else 0
    struct.pack_into("<III", b, 0x44, left, right, child)
    struct.pack_into("<I", b, 0x74, start)
    struct.pack_into("<Q", b, 0x78, size)
    return bytes(b)


class _Node:
    __slots__ = ("name", "type", "data", "start", "size", "left", "right", "child", "mini")

    def __init__(self, name, typ, data=b""):
        self.name = name
        self.type = typ
        self.data = data
        self.start = ENDOFCHAIN
        self.size = len(data)
        self.left = NOSTREAM
        self.right = NOSTREAM
        self.child = NOSTREAM
        self.mini = False


def _tree(nodes: list[_Node], lo: int, hi: int) -> int:
    if lo >= hi:
        return NOSTREAM
    mid = (lo + hi) // 2
    nodes[mid].left = _tree(nodes, lo, mid)
    nodes[mid].right = _tree(nodes, mid + 1, hi)
    return mid


def build(streams: list[tuple[str, bytes]]) -> bytes:
    root = _Node("Root Entry", 5)
    nodes = [root] + [_Node(n, 2, d) for n, d in streams]
    nodes[1:] = sorted(nodes[1:], key=lambda n: _key(n.name))
    root.child = _tree(nodes, 1, len(nodes))

    # ---- mini stream ----
    mini = bytearray()
    minifat: list[int] = []
    for n in nodes[1:]:
        if n.size < CUTOFF:
            n.mini = True
            first = len(mini) // MINI
            count = (n.size + MINI - 1) // MINI
            first_idx = len(minifat)
            for i in range(count):
                minifat.append(first_idx + i + 1 if i + 1 < count else ENDOFCHAIN)
            n.start = first
            mini += n.data + b"\0" * (count * MINI - n.size)
        # else regular; start assigned later
    root.size = len(mini)

    minifat_bytes = b"".join(struct.pack("<I", v) for v in minifat)
    minifat_bytes += b"\xff" * ((SECTOR - len(minifat_bytes) % SECTOR) % SECTOR)
    mini_bytes = bytes(mini) + b"\0" * ((SECTOR - len(mini) % SECTOR) % SECTOR)

    dir_bytes = b"".join(_entry(n.name, n.type, n.start, n.size, n.left, n.right, n.child) for n in nodes)
    dir_bytes += b"\0" * ((SECTOR - len(dir_bytes) % SECTOR) % SECTOR)

    regular = [n for n in nodes[1:] if not n.mini]
    reg_counts = [(n, (n.size + SECTOR - 1) // SECTOR) for n in regular]

    total = 0
    nfat = 1
    while True:
        ndir = len(dir_bytes) // SECTOR
        nmf = len(minifat_bytes) // SECTOR
        nmini = len(mini_bytes) // SECTOR
        ndata = sum(c for _, c in reg_counts)
        total = nfat + ndir + nmf + nmini + ndata
        need = (total * 4 + SECTOR - 1) // SECTOR
        if need <= nfat:
            break
        nfat = need

    fat_start = 0
    dir_start = fat_start + nfat
    minifat_start = dir_start + ndir
    mini_start = minifat_start + nmf
    data_start = mini_start + nmini

    fat = [FREESECT] * total
    for i in range(nfat):
        fat[fat_start + i] = FATSECT
    def chain(start: int, count: int):
        for i in range(count):
            fat[start + i] = start + i + 1 if i + 1 < count else ENDOFCHAIN
    chain(dir_start, ndir)
    chain(minifat_start, nmf)
    chain(mini_start, nmini)
    sec = data_start
    for n, count in reg_counts:
        n.start = sec
        chain(sec, count)
        sec += count
    root.start = mini_start if nmini else ENDOFCHAIN

    # rebuild directory now that starts are final
    dir_bytes = b"".join(_entry(n.name, n.type, n.start, n.size, n.left, n.right, n.child) for n in nodes)
    dir_bytes += b"\0" * (ndir * SECTOR - len(dir_bytes))

    header = bytearray(512)
    header[0:8] = bytes.fromhex("d0cf11e0a1b11ae1")
    struct.pack_into("<HHHHH", header, 0x18, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<I", header, 0x2C, nfat)
    struct.pack_into("<I", header, 0x30, dir_start)
    struct.pack_into("<I", header, 0x38, CUTOFF)
    struct.pack_into("<I", header, 0x3C, minifat_start)
    struct.pack_into("<I", header, 0x40, nmf)
    struct.pack_into("<I", header, 0x44, ENDOFCHAIN)
    struct.pack_into("<I", header, 0x48, 0)
    for i in range(109):
        struct.pack_into("<I", header, 0x4C + 4 * i, fat_start + i if i < nfat else FREESECT)

    fat_bytes = b"".join(struct.pack("<I", v) for v in fat)
    fat_bytes += b"\xff" * (nfat * SECTOR - len(fat_bytes))

    out = bytearray()
    out += header
    out += fat_bytes
    out += dir_bytes
    out += minifat_bytes
    out += mini_bytes
    for n, count in reg_counts:
        out += n.data + b"\0" * (count * SECTOR - n.size)
    return bytes(out)
