"""Build a synthetic .jnt/.jtp page from a template plus an InkStream XML."""
import struct, sys, zlib, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from jntread.nbtiff import NBDocument, CompressedBlob
from jntread.nbwrite import build
from jntread.cfbwrite import build as cfbbuild


def ink_stream_xml(xml: bytes, flags=0, width=7760, height=9458, line_height=460,
                   lang=1033, when=0x01C1EC7923BCD3A0, extra=b"") -> bytes:
    out = bytearray()
    out += struct.pack("<HI", 0x4000, flags)
    out += struct.pack("<HQ", 0x5000, when)
    out += struct.pack("<HII", 0x1000, width, height)
    out += struct.pack("<H", 0x2001) + struct.pack("<HII", 1, 0x12345678, len(xml)) + xml
    out += struct.pack("<H", 0xFFFF)
    return bytes(out)


def make(base: str, out: str, xml: bytes, **kw):
    d = NBDocument(open(base, 'rb').read())
    page = [(tag, e.type, e.raw) for tag, e in sorted(d.ifds[0].entries.items())]
    stream = ink_stream_xml(xml, **kw)
    cfb = cfbbuild([("InkStream", stream)])
    wrapper = struct.pack("<5I", 2, len(cfb), 1, 0xFFFFFFFF, 0) + zlib.compress(cfb)
    page = [(t, ty, wrapper if t == 0x9333 else raw) for t, ty, raw in page]
    open(out, 'wb').write(build([page], preamble=d.data[12:d.first_ifd]))
    return out


if __name__ == '__main__':
    xml = open(sys.argv[3], 'rb').read()
    make(sys.argv[1], sys.argv[2], xml)
    print('wrote', sys.argv[2])
