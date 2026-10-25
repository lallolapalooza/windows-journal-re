"""Patch streams inside the EP compound file and rebuild the NB container."""
import sys, os, struct, zlib, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))
from jntread.nbtiff import NBDocument
from jntread.nbwrite import build
from jntread.cfb import CFB
from jntread import cfbwrite
import eprops

BASE = os.path.join(os.path.dirname(__file__), '..', 'samples', 'blank.jtp')


def stream_file_offsets(cfb: CFB, entry):
    """Return [(file_offset, length)] of a stream's bytes inside cfb.data."""
    out = []
    if entry.size < cfb.mini_cutoff:
        # map mini-sector index -> offset inside the mini stream
        root = cfb.entries[0]
        # build ministream physical layout
        sec = root.start
        mini_secs = []
        seen = set()
        while sec <= 0xFFFFFFFA and sec not in seen:
            seen.add(sec); mini_secs.append(sec)
            if sec >= len(cfb._fat): break
            sec = cfb._fat[sec]
        # mini-sector -> (which ministream sector, offset within)
        start = entry.start
        remaining = entry.size
        seen = set()
        while remaining > 0 and start <= 0xFFFFFFFA and start not in seen:
            seen.add(start)
            mini_off = start * cfb.mini_sector_size
            sector_idx = mini_off // cfb.sector_size
            inner = mini_off % cfb.sector_size
            n = min(cfb.sector_size - inner, remaining)
            out.append((512 + mini_secs[sector_idx] * cfb.sector_size + inner, n))
            remaining -= n
            start = cfb._minifat[start] if start < len(cfb._minifat) else 0xFFFFFFFE
    else:
        start = entry.start
        remaining = entry.size
        seen = set()
        while remaining > 0 and start <= 0xFFFFFFFA and start not in seen:
            seen.add(start)
            n = min(cfb.sector_size, remaining)
            out.append((512 + start * cfb.sector_size, n))
            remaining -= n
            start = cfb._fat[start] if start < len(cfb._fat) else 0xFFFFFFFE
    return out


def find_entry(cfb, storage, name):
    for sname in (storage, '\x05' + storage):
        try:
            for path, e in cfb.iter_streams((sname,)):
                if path[-1] == name:
                    return e
        except Exception:
            pass
    raise KeyError((storage, name))


def patch_prop(blob: bytearray, storage: str, fmtid: str, prop: int, newbytes: bytes):
    """Patch a property value inside the EP compound file *blob* (in place)."""
    cfb = CFB.parse(bytes(blob))
    e = find_entry(cfb, storage, 'CONTENTS')
    raw = bytearray(cfb.read_stream(e))
    for fmt, off, size, np in eprops.sections(raw):
        if str(fmt) != fmtid: continue
        for pid, vt, p in eprops.read_props(raw, off):
            if pid != prop: continue
            cur = eprops.value_bytes(raw, vt, p)
            if len(cur) != len(newbytes):
                raise ValueError('size mismatch: %d vs %d' % (len(cur), len(newbytes)))
            raw[p+4:p+4+len(newbytes)] = newbytes
            # write back to blob
            for foff, n in stream_file_offsets(cfb, e):
                pass
            # simple: stream is contiguous in practice for the mini stream
            offs = stream_file_offsets(cfb, e)
            pos = 0
            for foff, n in offs:
                blob[foff:foff+n] = raw[pos:pos+n]
                pos += n
            return bytes(blob)
    raise KeyError(prop)


def rebuild(page, ep_blob=None, inkstream=None, reco=None):
    d = NBDocument(open(BASE, 'rb').read())
    tags = [(t, e.type, e.raw) for t, e in sorted(d.ifds[0].entries.items())]
    out = []
    for t, ty, raw in tags:
        if t == 0x9330 and ep_blob is not None:
            raw = ep_blob
        if t == 0x9333 and inkstream is not None:
            cfb = cfbwrite.build([('InkStream', inkstream)])
            raw = struct.pack('<5I', 2, len(cfb), 1, 0xFFFFFFFF, 0) + zlib.compress(cfb)
        out.append((t, ty, raw))
    data = build([out], preamble=d.data[12:d.first_ifd])
    open(page, 'wb').write(data)
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'oracle_direct.py'), page],
                       capture_output=True)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')


def patch_value_bytes(blob: bytearray, storage: str, fmtid: str, prop: int, off_in_value: int, newbytes: bytes):
    cfb = CFB.parse(bytes(blob))
    e = find_entry(cfb, storage, 'CONTENTS')
    raw = bytearray(cfb.read_stream(e))
    for fmt, off, size, np in eprops.sections(raw):
        if str(fmt) != fmtid: continue
        for pid, vt, p in eprops.read_props(raw, off):
            if pid != prop: continue
            hdr = 8 if vt == 0x41 else 4
            pos = p + hdr + off_in_value
            raw[pos:pos+len(newbytes)] = newbytes
            offs = stream_file_offsets(cfb, e)
            pos2 = 0
            for foff, n in offs:
                blob[foff:foff+n] = raw[pos2:pos2+n]
                pos2 += n
            return bytes(blob)
    raise KeyError(prop)
