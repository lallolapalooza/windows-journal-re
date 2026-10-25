"""Minimal OLE Compound File Binary (MS-CFB) reader.

Only the read path is implemented: header, FAT/DIFAT chains, directory
tree and stream extraction (including the mini stream).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

CFB_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
MAXREGSECT = 0xFFFFFFFA

TYPE_EMPTY, TYPE_STORAGE, TYPE_STREAM, TYPE_ROOT = 0, 1, 2, 5


class CFBError(ValueError):
    pass


@dataclass
class DirEntry:
    name: str
    type: int
    left: int
    right: int
    child: int
    start: int
    size: int
    clsid: bytes = b""
    state: int = 0
    creation: int = 0
    modified: int = 0


@dataclass
class CFB:
    data: bytes
    sector_size: int = 512
    mini_sector_size: int = 64
    mini_cutoff: int = 4096
    entries: list[DirEntry] = field(default_factory=list)
    _fat: list[int] = field(default_factory=list)
    _minifat: list[int] = field(default_factory=list)
    _ministream: bytes | None = None

    @classmethod
    def parse(cls, data: bytes) -> "CFB":
        if len(data) < 512 or data[:8] != CFB_MAGIC:
            raise CFBError("not a compound file")
        (minor, major, byteorder, sshift, mshift) = struct.unpack_from("<HHHHH", data, 0x18)
        if byteorder != 0xFFFE:
            raise CFBError("bad byte order")
        self = cls(data=data)
        self.sector_size = 1 << sshift
        self.mini_sector_size = 1 << mshift
        self.mini_cutoff = struct.unpack_from("<I", data, 0x38)[0]
        n_fat = struct.unpack_from("<I", data, 0x2C)[0]
        first_dir = struct.unpack_from("<I", data, 0x30)[0]
        first_minifat = struct.unpack_from("<I", data, 0x3C)[0]
        n_minifat = struct.unpack_from("<I", data, 0x40)[0]
        first_difat = struct.unpack_from("<I", data, 0x44)[0]
        n_difat = struct.unpack_from("<I", data, 0x48)[0]

        # DIFAT: 109 header entries + chained sectors.
        difat = list(struct.unpack_from("<109I", data, 0x4C))
        sec = first_difat
        seen = set()
        while sec <= MAXREGSECT and n_difat and sec not in seen:
            seen.add(sec)
            raw = self._sector(sec)
            vals = struct.unpack("<%dI" % (self.sector_size // 4), raw)
            difat.extend(vals[:-1])
            sec = vals[-1]
        difat = [s for s in difat if s <= MAXREGSECT][:n_fat]

        fat = []
        for s in difat:
            raw = self._sector(s)
            fat.extend(struct.unpack("<%dI" % (self.sector_size // 4), raw))
        self._fat = fat

        # Directory.
        dirdata = bytearray()
        for s in self._chain(first_dir):
            dirdata += self._sector(s)
        for off in range(0, len(dirdata) - 127, 128):
            e = dirdata[off:off + 128]
            nlen = struct.unpack_from("<H", e, 0x40)[0]
            name = e[: max(0, nlen - 2)].decode("utf-16-le", "replace")
            typ = e[0x42]
            left, right, child = struct.unpack_from("<III", e, 0x44)
            clsid = e[0x50:0x60]
            state = struct.unpack_from("<I", e, 0x60)[0]
            ctime, mtime = struct.unpack_from("<QQ", e, 0x64)
            start = struct.unpack_from("<I", e, 0x74)[0]
            size = struct.unpack_from("<Q", e, 0x78)[0]
            self.entries.append(DirEntry(name, typ, left, right, child, start, size,
                                         clsid, state, ctime, mtime))
        if not self.entries or self.entries[0].type != TYPE_ROOT:
            raise CFBError("no root entry")
        self._minifat = self._read_fat_chain_list(first_minifat, n_minifat)

        root = self.entries[0]
        self._ministream = b"".join(self._sector(s) for s in self._chain(root.start, root.size))
        return self

    # -- low level -----------------------------------------------------
    def _sector(self, index: int) -> bytes:
        off = 512 + index * self.sector_size
        if off + self.sector_size > len(self.data):
            raise CFBError("sector out of range: %d" % index)
        return self.data[off:off + self.sector_size]

    def _chain(self, start: int, size: int | None = None):
        if start > MAXREGSECT:
            return
        seen = set()
        sec = start
        while sec <= MAXREGSECT and sec not in seen:
            seen.add(sec)
            yield sec
            if size is not None and len(seen) * self.sector_size >= size:
                return
            if sec >= len(self._fat):
                return
            sec = self._fat[sec]

    def _read_fat_chain_list(self, start: int, count: int) -> list[int]:
        out: list[int] = []
        for s in self._chain(start):
            out.extend(struct.unpack("<%dI" % (self.sector_size // 4), self._sector(s)))
        if count:
            per = self.sector_size // 4
            return out[: count * per]
        return out

    def read_stream(self, entry: DirEntry) -> bytes:
        if entry.type != TYPE_STREAM:
            raise CFBError("not a stream")
        if entry.size < self.mini_cutoff:
            out = bytearray()
            sec = entry.start
            seen = set()
            while sec <= MAXREGSECT and sec not in seen:
                seen.add(sec)
                off = sec * self.mini_sector_size
                out += self._ministream[off:off + self.mini_sector_size]
                if len(out) >= entry.size:
                    break
                if sec >= len(self._minifat):
                    break
                sec = self._minifat[sec]
            return bytes(out[: entry.size])
        return b"".join(self._sector(s) for s in self._chain(entry.start, entry.size))[: entry.size]

    # -- high level ----------------------------------------------------
    def _child_of(self, index: int):
        e = self.entries[index]
        stack = [e.child]
        while stack:
            i = stack.pop()
            if i == FREESECT or i >= len(self.entries):
                continue
            cur = self.entries[i]
            yield cur
            stack.append(cur.left)
            stack.append(cur.right)

    def iter_streams(self, path: tuple[str, ...] = ()):
        """Yield ((storage, ..., name), DirEntry) for every stream."""
        root = self.entries[0]
        if not path:
            children = list(self._child_of(0))
        else:
            children = []
            node = None
            for c in self._child_of(0):
                if c.name == path[0] and c.type == TYPE_STORAGE:
                    node = c
                    break
            if node is None:
                return
            idx = self.entries.index(node)
            children = list(self._child_of(idx))
            if len(path) > 1:
                # descend iteratively
                cur = node
                rest = list(path[1:])
                while rest:
                    nxt = None
                    for c in self._child_of(self.entries.index(cur)):
                        if c.name == rest[0] and c.type == TYPE_STORAGE:
                            nxt = c
                            break
                    if nxt is None:
                        return
                    cur = nxt
                    rest.pop(0)
                children = list(self._child_of(self.entries.index(cur)))
                yield from (((path + (c.name,)), c) for c in children if c.type == TYPE_STREAM)
                return
        for c in children:
            if c.type == TYPE_STREAM:
                yield (path + (c.name,), c)
            elif c.type == TYPE_STORAGE:
                yield from self.iter_streams(path + (c.name,))

    def open_stream(self, name: str, storage: str | None = None) -> bytes:
        for path, entry in self.iter_streams((storage,) if storage else ()):
            if path[-1] == name:
                return self.read_stream(entry)
        raise KeyError(name)
