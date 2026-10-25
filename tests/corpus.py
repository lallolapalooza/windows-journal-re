"""Build synthetic .jnt files exercising every Journal Reader element and compare
our reader against the shipped reference implementation (scripts/oracle_direct.py)."""
import sys, os, struct, zlib, subprocess, base64, difflib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from jntread.nbtiff import NBDocument
from jntread.nbwrite import build as nbbuild
from jntread.cfbwrite import build as cfbbuild
from jntread.document import Document
from jntread.xmlexport import document_xml
from jntread.stationery import Stationery

BASE = os.path.join(ROOT, 'samples', 'blank.jtp')
if not os.path.exists(BASE):
    print('skipped: requires extracted Microsoft samples (see tests/README.md)')
    raise SystemExit(0)
ISF = open(os.path.join(ROOT, 'out', 'stroke.isf'), 'rb').read()
ISF_B64 = base64.b64encode(ISF).decode()


def stationery_blob(bg=1, h=1, v=1, margin=1, title=2, date=1, img_style=1, fade=0, mtype=0,
                    colors=((0x11, 0x22, 0x33), (0x44, 0x55, 0x66), (0x77, 0x88, 0x99),
                            (0xAA, 0xBB, 0xCC), (0xDD, 0xEE, 0xFF)),
                    floats=(0.5, 1.25, 0.25, 0.75, 2.0, 0.125, 7.5, 0.125, 1.0),
                    name="", image=b"") -> bytes:
    out = bytearray(b"\x02\x30")
    out += struct.pack("<9H", bg, h, v, margin, title, date, img_style, fade, mtype)
    out += b"\0\0"
    for c in colors:
        out += bytes(c) + b"\0"
    out += struct.pack("<9f", *floats)
    nb = name.encode("utf-16-le") + b"\0\0"
    out += struct.pack("<I", len(nb)) + nb
    out += struct.pack("<II", len(image), 0) + image
    return bytes(out)


def ink_stream(xml: str, title="", date="", stationery: bytes | None = None,
               flags=0, width=7760, height=9458, line_height=460, lang=1033) -> bytes:
    out = bytearray()
    out += struct.pack("<HI", 0x4000, flags)
    out += struct.pack("<HQ", 0x5000, 0x01C1EC7923BCD3A0)
    out += struct.pack("<HII", 0x1000, width, height)
    if date or title:
        out += struct.pack("<H", 0x7000)
        for s in (date, title):
            b = s.encode("utf-16-le")
            out += struct.pack("<I", len(b) + 2) + b + b"\0\0"
    if stationery is not None:
        out += struct.pack("<H", 0x3002) + stationery[2:]  # tag already in blob
    xb = xml.encode()
    out += struct.pack("<H", 0x2001) + struct.pack("<H", 1) + struct.pack("<I", 0x12345678)
    out += struct.pack("<I", len(xb)) + xb + b"\0"
    out += struct.pack("<H", 0)  # no second XML
    out += struct.pack("<H", 0xFFFF)
    return bytes(out)


def wrap(content: str, width=7760, height=9458, line_height=460, lang=1033) -> str:
    return ('<InkSegment xmlns="urn:schemas-microsoft-com:tabletpc:richink">'
            '<Version>1</Version><SegmentWidth>%d</SegmentWidth><SegmentHeight>%d</SegmentHeight>'
            '<SegmentLineHeight>%d</SegmentLineHeight><EmusPerHostUnit>914.4</EmusPerHostUnit>'
            '<LanguageID>%d</LanguageID><Content>%s</Content></InkSegment>'
            % (width, height, line_height, lang, content))


def build_file(path, streams, pages=1):
    d = NBDocument(open(BASE, 'rb').read())
    page_tags = [(t, e.type, e.raw) for t, e in sorted(d.ifds[0].entries.items())]
    newpages = []
    for st in streams:
        cfb = cfbbuild([("InkStream", st)])
        wrapped = struct.pack("<5I", 2, len(cfb), 1, 0xFFFFFFFF, 0) + zlib.compress(cfb)
        newpages.append([(t, ty, wrapped if t == 0x9333 else raw) for t, ty, raw in page_tags])
    open(path, "wb").write(nbbuild(newpages, preamble=d.data[12:d.first_ifd]))


def oracle(path):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "oracle_direct.py"), path],
                       capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace")


CASES = {
 "text": '<HostedNode><BoundingRect X="100" Y="90" Width="500" Height="200"/>'
         '<Guid>{29C4CC4F-5A37-4D53-9FE4-F74731B2D444}</Guid>'
         '<HostedBoundingRect X="100" Y="90" Width="500" Height="200"/>'
         '<HostedContent><Text>Hello &amp; goodbye</Text></HostedContent></HostedNode>',
 "image": '<HostedNode><BoundingRect X="10" Y="20" Width="300" Height="400"/>'
          '<Guid>{A201ECB0-0C0A-4C81-84E4-D82614E2ACBA}</Guid>'
          '<HostedBoundingRect X="10" Y="20" Width="300" Height="400"/>'
          '<HostedContent><Image>base64:' + ISF_B64 + '</Image></HostedContent></HostedNode>',
 "flag": '<HostedNode><BoundingRect X="1" Y="2" Width="30" Height="40"/>'
         '<Guid>{EBD73B02-79E6-4899-B70C-DD185CF4E26B}</Guid>'
         '<HostedBoundingRect X="1" Y="2" Width="30" Height="40"/>'
         '<HostedContent><Image>base64:' + ISF_B64 + '</Image></HostedContent></HostedNode>',
 "inkword": '<InkWord><BoundingRect X="10" Y="20" Width="300" Height="400"/>'
            '<ScalarTransform Mat1="1" Mat2="0" Mat3="0" Mat4="0" Mat5="1" Mat6="0" Mat7="0" Mat8="0" Mat9="1"/>'
            '<CanReclassify>true</CanReclassify><InkClass>Word</InkClass><Confidence>2</Confidence>'
            '<Pinned>true</Pinned><InkObject>base64:' + ISF_B64 + '</InkObject></InkWord>',
 "drawing": '<Drawing><BoundingRect X="10" Y="20" Width="300" Height="400"/>'
            '<InkObject>base64:' + ISF_B64 + '</InkObject></Drawing>',
 "alternates": '<InkWord><BoundingRect X="10" Y="20" Width="300" Height="400"/>'
               '<AlternateList><Alternate>hello</Alternate><Alternate>help</Alternate></AlternateList>'
               '<InkObject>base64:' + ISF_B64 + '</InkObject></InkWord>',
 "group": '<GroupNode><BoundingRect X="0" Y="0" Width="1000" Height="1000"/>'
          '<InkWord><BoundingRect X="10" Y="20" Width="300" Height="400"/>'
          '<InkObject>base64:' + ISF_B64 + '</InkObject></InkWord>'
          '<Drawing><BoundingRect X="100" Y="200" Width="300" Height="400"/>'
          '<InkObject>base64:' + ISF_B64 + '</InkObject></Drawing></GroupNode>',
 "paragraph": '<Paragraph BlockNumber="3"><Line LineNumber="1">'
              '<InkWord><BoundingRect X="10" Y="20" Width="300" Height="400"/>'
              '<InkObject>base64:' + ISF_B64 + '</InkObject></InkWord>'
              '<ParagraphLineMetrics><Baseline PointA="10,20" PointB="300,420"/></ParagraphLineMetrics>'
              '</Line></Paragraph>',
 "reflow": '<Reflow><GroupNode><BoundingRect X="0" Y="0" Width="1000" Height="1000"/></GroupNode>'
           '<InkWord><BoundingRect X="10" Y="20" Width="300" Height="400"/>'
           '<InkObject>base64:' + ISF_B64 + '</InkObject></InkWord></Reflow>',
 "mixed": '<HostedNode><BoundingRect X="0" Y="0" Width="100" Height="100"/>'
          '<Guid>{29C4CC4F-5A37-4D53-9FE4-F74731B2D444}</Guid>'
          '<HostedBoundingRect X="0" Y="0" Width="100" Height="100"/>'
          '<HostedContent><Text>Title-ish</Text></HostedContent></HostedNode>'
          '<Paragraph BlockNumber="0"><Line LineNumber="0">'
          '<InkWord><BoundingRect X="10" Y="20" Width="30" Height="40"/>'
          '<InkObject>base64:' + ISF_B64 + '</InkObject></InkWord></Line></Paragraph>'
          '<Drawing><BoundingRect X="5" Y="6" Width="7" Height="8"/><InkObject>base64:' + ISF_B64 + '</InkObject></Drawing>',
}


def main():
    ok = total = 0
    for name, content in CASES.items():
        for mode in ("plain", "title", "stationery"):
            kw = {}
            if mode == "title":
                kw = dict(title="Hello Title", date="1/2/2020 3:04:05 AM")
            if mode == "stationery":
                kw = dict(stationery=stationery_blob())
            xml = wrap(content)
            path = os.path.join(ROOT, "out", "corpus_%s_%s.jnt" % (name, mode))
            build_file(path, [ink_stream(xml, **kw)])
            rc, ref = oracle(path)
            total += 1
            if rc != 0:
                print("%-24s oracle-failed" % (name + "/" + mode))
                continue
            got = document_xml(Document.parse(open(path, "rb").read()))
            if got == ref:
                ok += 1
                print("%-24s OK" % (name + "/" + mode))
            else:
                i = 0
                while i < min(len(ref), len(got)) and ref[i] == got[i]:
                    i += 1
                print("%-24s DIFF at %d" % (name + "/" + mode, i))
                print("  ref:", ref[max(0, i-80):i+200])
                print("  got:", got[max(0, i-80):i+200])
    # multi-page
    xml = wrap(CASES["inkword"])
    path = os.path.join(ROOT, "out", "corpus_multipage.jnt")
    build_file(path, [ink_stream(xml), ink_stream(xml)])
    rc, ref = oracle(path)
    total += 1
    if rc == 0:
        got = document_xml(Document.parse(open(path, "rb").read()))
        if got == ref:
            ok += 1
            print("%-24s OK (pages=%d)" % ("multipage", got.count("<JournalPage ")))
        else:
            print("%-24s DIFF (pages ref=%d ours=%d)" % ("multipage", ref.count("<JournalPage "), got.count("<JournalPage ")))
    else:
        print("%-24s oracle-failed" % "multipage")
    print("%d/%d OK" % (ok, total))


if __name__ == "__main__":
    main()
