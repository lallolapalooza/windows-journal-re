import sys, os, struct, zlib, subprocess, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from jntread.nbtiff import NBDocument
from jntread.nbwrite import build
from jntread.cfbwrite import build as cfbbuild

BASE = os.path.join(os.path.dirname(__file__), '..', 'samples', 'blank.jtp')

def wrap_content(inner: str) -> str:
    return ('<InkSegment xmlns="urn:schemas-microsoft-com:tabletpc:richink">'
            '<Version>1</Version><SegmentWidth>7760</SegmentWidth><SegmentHeight>9458</SegmentHeight>'
            '<SegmentLineHeight>460</SegmentLineHeight><EmusPerHostUnit>914.4</EmusPerHostUnit>'
            '<LanguageID>1033</LanguageID><Content>' + inner + '</Content></InkSegment>')

def build_file(xml: str, path: str):
    d = NBDocument(open(BASE, 'rb').read())
    xb = xml.encode()
    st = bytearray()
    st += struct.pack('<HI', 0x4000, 0)
    st += struct.pack('<HQ', 0x5000, 0x01C1EC7923BCD3A0)
    st += struct.pack('<HII', 0x1000, 7760, 9458)
    st += struct.pack('<H', 0x2001) + struct.pack('<HII', 1, 0x12345678, len(xb)) + xb + b'\0\0\0'
    st += struct.pack('<H', 0xFFFF)
    cfb = cfbbuild([('InkStream', bytes(st))])
    w = struct.pack('<5I', 2, len(cfb), 1, 0xFFFFFFFF, 0) + zlib.compress(cfb)
    page = [(t, e.type, (w if t == 0x9333 else e.raw)) for t, e in sorted(d.ifds[0].entries.items())]
    open(path, 'wb').write(build([page], preamble=d.data[12:d.first_ifd]))

def probe(inner: str):
    path = 'out/probe.jtp'
    build_file(wrap_content(inner), path)
    r = subprocess.run([sys.executable, 'scripts/oracle_direct.py', path], capture_output=True)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')

if __name__ == '__main__':
    cases = {
        'group_empty': '<GroupNode><BoundingRect Left="0" Top="0" Width="10" Height="10"/></GroupNode>',
        'group_content': '<GroupNode><BoundingRect Left="0" Top="0" Width="10" Height="10"/><Content/></GroupNode>',
        'paragraph': '<Paragraph BlockNumber="0"><Line LineNumber="0"><ParagraphLineMetrics><Baseline PointA="0,0" PointB="10,0"/></ParagraphLineMetrics></Line></Paragraph>',
        'inkword': '<InkWord><BoundingRect Left="0" Top="0" Width="10" Height="10"/><InkObject></InkObject></InkWord>',
        'drawing': '<Drawing><BoundingRect Left="0" Top="0" Width="10" Height="10"/></Drawing>',
    }
    for k, v in cases.items():
        rc, out, err = probe(v)
        print('##', k, 'rc', rc)
        print('  err', err.strip().splitlines()[-1:] if err else '')
        print('  out', out[-400:] if out else '')
