import os, sys, unittest, struct, zlib, base64
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
from jntread.cfb import CFB
from jntread.cfbwrite import build as cfb_build
from jntread.nbtiff import NBDocument
from jntread.nbwrite import build as nb_build
from jntread.document import Document
from jntread.inkstream import InkStream
from jntread.stationery import Stationery
from jntread.xmlexport import document_xml
from jntread.isf import parse as parse_isf
from jntread.richink import parse as parse_richink

SAMPLES = os.path.join(ROOT, 'samples')
HAS_SAMPLES = os.path.isdir(SAMPLES)


def make_stationery():
    out = bytearray(b'\x02\x30')
    out += struct.pack('<9H', 1, 1, 1, 1, 2, 1, 1, 0, 0)
    out += b'\0\0'
    for c in ((255, 255, 255), (0x11, 0x22, 0x33), (0x44, 0x55, 0x66),
              (0x77, 0x88, 0x99), (0xAA, 0xBB, 0xCC)):
        out += bytes(c) + b'\0'
    out += struct.pack('<9f', 0.5, 1.25, 0.25, 0.75, 0.125, 0.125, 7.5, 0.125, 1.0)
    name = 'paper.emf'.encode('utf-16-le') + b'\0\0'
    out += struct.pack('<I', len(name)) + name
    out += struct.pack('<II', 4, 0) + b'EMF!'
    return bytes(out)


def make_inkstream():
    xml = ('<InkSegment xmlns="urn:schemas-microsoft-com:tabletpc:richink">'
           '<Version>1</Version><SegmentWidth>7760</SegmentWidth><SegmentHeight>9458</SegmentHeight>'
           '<SegmentLineHeight>460</SegmentLineHeight><EmusPerHostUnit>914.4</EmusPerHostUnit>'
           '<LanguageID>1033</LanguageID><Content>'
           '<InkWord><BoundingRect X="100" Y="120" Width="20" Height="30"/>'
           '<InkObject>base64:AB4dAhQIAwRIEEU1ChIGChkIwtDcQRLACTIgi0jDclg=</InkObject></InkWord>'
           '</Content></InkSegment>').encode()
    out = bytearray()
    out += struct.pack('<HI', 0x4000, 2)
    out += struct.pack('<HQ', 0x5000, 0x01C1EC7923BCD3A0)
    out += struct.pack('<HII', 0x1000, 7760, 9458)
    for s in ('1/2/2020 3:04:05 AM', 'Hello'):
        b = s.encode('utf-16-le')
        out += struct.pack('<I', len(b) + 2) + b + b'\0\0'
    out = bytearray(struct.pack('<H', 0x7000)) + out[0:] if False else out
    # The 0x7000 tag must precede the two strings; rebuild cleanly.
    out = bytearray()
    out += struct.pack('<HI', 0x4000, 2)
    out += struct.pack('<HQ', 0x5000, 0x01C1EC7923BCD3A0)
    out += struct.pack('<HII', 0x1000, 7760, 9458)
    out += struct.pack('<H', 0x7000)
    for s in ('1/2/2020 3:04:05 AM', 'Hello'):
        b = s.encode('utf-16-le')
        out += struct.pack('<I', len(b) + 2) + b + b'\0\0'
    out += struct.pack('<H', 0x3002) + make_stationery()[2:]
    out += struct.pack('<H', 0x2001) + struct.pack('<H', 1) + struct.pack('<I', 0x12345678)
    out += struct.pack('<I', len(xml)) + xml + b'\0'
    out += struct.pack('<H', 0) + struct.pack('<H', 0xFFFF)
    return bytes(out)


def make_document_bytes():
    cfb = cfb_build([('InkStream', make_inkstream())])
    wrapper = struct.pack('<5I', 2, len(cfb), 1, 0xFFFFFFFF, 0) + zlib.compress(cfb)
    return nb_build([[(0x9333, 7, wrapper)]])


class TestCFB(unittest.TestCase):
    def test_roundtrip_small_and_large(self):
        for payload in (b'hello' * 3, b'x' * 9000, bytes(range(256)) * 40):
            cfb = CFB.parse(cfb_build([('InkStream', payload), ('Other', b'abc')]))
            streams = {p[-1]: cfb.read_stream(e) for p, e in cfb.iter_streams()}
            self.assertEqual(streams['InkStream'], payload)
            self.assertEqual(streams['Other'], b'abc')

    @unittest.skipUnless(HAS_SAMPLES, 'requires extracted Microsoft samples')
    def test_nested_storage(self):
        nb = NBDocument(open(os.path.join(SAMPLES, 'blank.jtp'), 'rb').read())
        cfb = CFB.parse(nb.ep_page())
        names = {p[-1] for p, _ in cfb.iter_streams()}
        self.assertIn('CONTENTS', names)


class TestContainer(unittest.TestCase):
    def test_nb_header_and_ifd(self):
        data = make_document_bytes()
        nb = NBDocument(data)
        self.assertEqual(nb.signature, b'NB')
        self.assertEqual(nb.tiff_magic, 42)
        self.assertEqual(nb.version, 0x10000150)
        self.assertEqual(nb.page_count, 1)
        self.assertIn(0x9333, nb.ifds[0].entries)
        self.assertEqual(nb.ink_stream(0)[:8], bytes.fromhex('d0cf11e0a1b11ae1'))

    def test_stationery_roundtrip(self):
        st = Stationery.parse(make_stationery())
        self.assertEqual((st.bg_style, st.title_style, st.date_style), (1, 2, 1))
        self.assertEqual(st.image_style, 1)
        self.assertEqual(st.bg_color, (255, 255, 255))
        self.assertAlmostEqual(st.title_right, 7.5, places=5)
        self.assertEqual(st.image_name, 'paper.emf')
        self.assertEqual(st.image_data, b'EMF!')

    @unittest.skipUnless(HAS_SAMPLES, 'requires extracted Microsoft samples')
    def test_rebuild_roundtrip(self):
        data = open(os.path.join(SAMPLES, 'blank.jtp'), 'rb').read()
        nb = NBDocument(data)
        page = [(t, e.type, e.raw) for t, e in sorted(nb.ifds[0].entries.items())]
        rebuilt = nb_build([page], preamble=data[12:nb.first_ifd])
        again = NBDocument(rebuilt)
        self.assertEqual(sorted(again.ifds[0].entries), sorted(nb.ifds[0].entries))
        self.assertEqual(again.ifds[0].entries[0x9333].raw, nb.ifds[0].entries[0x9333].raw)


class TestDocument(unittest.TestCase):
    def test_synthetic_document(self):
        doc = Document.parse(make_document_bytes())
        page = doc.pages[0]
        self.assertEqual(page.number, 1)
        self.assertEqual(page.ink.title_text, 'Hello')
        self.assertEqual(page.ink.date_text, '1/2/2020 3:04:05 AM')
        self.assertIsNotNone(page.ink.stationery)
        self.assertIsNotNone(page.segment)
        self.assertEqual(page.segment.width, 7760)
        xml = document_xml(doc)
        self.assertIn('<JournalPage Number="1" Width="19710" Height="24023" LineHeight="1168"', xml)
        self.assertIn('<Text>Hello</Text><Date>2020-01-02T03:04:05</Date>', xml)
        self.assertIn('<InkWord Left="254" Top="305" Width="51" Height="76">', xml)

    @unittest.skipUnless(HAS_SAMPLES, 'requires extracted Microsoft samples')
    def test_blank_stationery(self):
        doc = Document.parse(open(os.path.join(SAMPLES, 'blank.jtp'), 'rb').read())
        self.assertEqual(doc.default_width, 19711)
        self.assertEqual(doc.default_height, 24024)
        self.assertEqual(round(doc.stationery.title_left * 2540), 318)


class TestRichInk(unittest.TestCase):
    XML = ('<InkSegment xmlns="urn:schemas-microsoft-com:tabletpc:richink">'
           '<Version>1</Version><SegmentWidth>100</SegmentWidth><SegmentHeight>200</SegmentHeight>'
           '<SegmentLineHeight>10</SegmentLineHeight><EmusPerHostUnit>914.4</EmusPerHostUnit>'
           '<LanguageID>1033</LanguageID><Content>'
           '<GroupNode><BoundingRect X="1" Y="2" Width="3" Height="4"/>'
           '<Paragraph BlockNumber="2"><Line LineNumber="3">'
           '<InkWord><BoundingRect X="5" Y="6" Width="7" Height="8"/><InkObject/></InkWord>'
           '<ParagraphLineMetrics><Baseline PointA="1,2" PointB="3,4"/></ParagraphLineMetrics>'
           '</Line></Paragraph>'
           '<HostedNode><BoundingRect X="0" Y="0" Width="1" Height="1"/>'
           '<Guid>{29C4CC4F-5A37-4D53-9FE4-F74731B2D444}</Guid>'
           '<HostedContent><Text>hi</Text></HostedContent></HostedNode>'
           '<Reflow><Drawing><BoundingRect X="0" Y="0" Width="2" Height="2"/><InkObject/></Drawing></Reflow>'
           '</GroupNode></Content></InkSegment>')

    def test_kinds(self):
        seg = parse_richink(self.XML)
        self.assertEqual([n.kind for n in seg.content], ['GroupNode'])
        group = seg.content[0]
        self.assertEqual([c.kind for c in group.children], ['Paragraph', 'HostedNode', 'Reflow'])
        self.assertEqual(group.children[0].block_number, 2)
        self.assertEqual(group.children[0].lines[0].line_number, 3)
        self.assertEqual(group.children[1].text, 'hi')


class TestISF(unittest.TestCase):
    def test_bitpack_points(self):
        data = bytes.fromhex('00 13 1d 02 04 04 03 04 48 10 45 35 0a 07 02 08 64 6e 08 64 6b')
        ink = parse_isf(data)
        self.assertEqual(len(ink.strokes), 1)
        self.assertEqual(ink.strokes[0].points, [(100, 100), (110, 107)])

    def test_huffman_is_flagged(self):
        data = bytes.fromhex('00 17 1d 02 06 06 03 04 48 10 45 35 0a 0b 04 82 fd 59 fa 64 82 fd 59 fa 7c')
        ink = parse_isf(data)
        self.assertEqual(len(ink.strokes), 1)
        self.assertTrue(ink.strokes[0].huffman)
        self.assertEqual(ink.strokes[0].points, [])


if __name__ == '__main__':
    unittest.main()
