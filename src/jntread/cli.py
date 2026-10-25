"""Command-line interface for the Windows Journal reader."""
from __future__ import annotations

import argparse
import base64
import json
import sys

from .document import Document, Page
from .richink import Node, Segment
from .stationery import Stationery, BG_STYLES, LINE_STYLES, TITLE_STYLES, DATE_STYLES, IMAGE_STYLES, MARGIN_TYPES
from .xmlexport import document_xml, parse_date


def _rect(r):
    return {"x": r.x, "y": r.y, "width": r.width, "height": r.height}


def _node(n: Node) -> dict:
    out = {"type": n.kind, "bounds": _rect(n.rect)}
    if n.transform:
        out["scalar_transform"] = n.transform
    if n.alternates:
        out["alternates"] = n.alternates
    if n.can_reclassify is not None:
        out["can_reclassify"] = n.can_reclassify
    if n.ink_class is not None:
        out["ink_class"] = n.ink_class
    if n.confidence is not None:
        out["confidence"] = n.confidence
    if n.pinned is not None:
        out["pinned"] = n.pinned
    if n.ink:
        out["ink_object_base64"] = base64.b64encode(n.ink).decode()
        out["ink_object_size"] = len(n.ink)
        out["strokes"] = [
            {"points": [[x, y] for x, y in s.points], "point_count": s.c_points,
             "compression": ("huffman" if s.huffman else "bitpack"),
             "algorithm": s.algorithm, "encoded_size": len(s.encoded)}
            for s in n.ink_strokes
        ]
        if n.ink_warnings:
            out["ink_warnings"] = n.ink_warnings
    if n.kind == "Line":
        out["line_number"] = n.line_number
    if n.kind == "Paragraph":
        out["block_number"] = n.block_number
        out["lines"] = [_node(line) for line in n.lines]
        if n.metrics is not None:
            out["metrics"] = n.metrics
    if n.guid:
        out["guid"] = n.guid
    if n.text:
        out["text"] = n.text
    if n.image:
        out["image_base64"] = base64.b64encode(n.image).decode()
    if n.children:
        out["children"] = [_node(c) for c in n.children]
    return out


def _stationery(st: Stationery | None) -> dict | None:
    if st is None:
        return None
    return {
        "background": {
            "style": BG_STYLES.get(st.bg_style, ""),
            "color": "#%02x%02x%02x" % st.bg_color,
            "image": ({"style": IMAGE_STYLES.get(st.image_style, ""), "fade": st.image_fade,
                       "path": st.image_name, "size": len(st.image_data),
                       "base64": base64.b64encode(st.image_data).decode()}
                      if (st.image_name or st.image_data) else None),
        },
        "title": {
            "style": TITLE_STYLES.get(st.title_style, ""),
            "date_style": DATE_STYLES.get(st.date_style, ""),
            "color": "#%02x%02x%02x" % st.title_color,
            "area": {"left": st.title_left, "top": st.title_top,
                     "right": st.title_right, "bottom": st.title_bottom},
        },
        "lines": {
            "horizontal": {"style": LINE_STYLES.get(st.h_style, ""),
                           "color": "#%02x%02x%02x" % st.h_color,
                           "spacing_before": st.h_before, "spacing_between": st.h_between},
            "vertical": {"style": LINE_STYLES.get(st.v_style, ""),
                         "color": "#%02x%02x%02x" % st.v_color,
                         "spacing_before": st.v_before, "spacing_between": st.v_between},
            "margin": {"style": LINE_STYLES.get(st.margin_style, ""),
                       "color": "#%02x%02x%02x" % st.margin_color,
                       "type": MARGIN_TYPES.get(st.margin_type, ""),
                       "spacing": st.margin_spacing},
        },
    }


def _page(page: Page) -> dict:
    seg: Segment | None = page.segment
    out = {
        "number": page.number,
        "width_himetric": int(seg.width * 2.54) if seg else 0,
        "height_himetric": int(seg.height * 2.54) if seg else 0,
        "line_height_himetric": int(seg.line_height * 2.54) if seg and seg.line_height else 0,
        "language_id": seg.language_id if seg else 0,
        "title": {
            "text": page.ink.title_text if page.ink else "",
            "date": parse_date(page.ink.date_text if page.ink else ""),
        },
        "stationery": _stationery(page.ink.stationery if page.ink else None),
        "content": [_node(n) for n in seg.content] if seg else [],
        "has_richink_xml": seg is not None,
        "recognition_xml": page.reco_xml or None,
    }
    if page.ep_stationery is not None:
        out["ep_stationery"] = _stationery(page.ep_stationery)
    return out


def document_json(doc: Document) -> dict:
    return {
        "signature": doc.nb.signature.decode("latin1"),
        "container_version": doc.nb.version,
        "page_count": doc.nb.page_count,
        "default_page_width_himetric": doc.default_width,
        "default_page_height_himetric": doc.default_height,
        "stationery": _stationery(doc.stationery),
        "pages": [_page(p) for p in doc.pages],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jntread", description="Read Windows Journal .jnt/.jtp files")
    ap.add_argument("file", help=".jnt or .jtp file")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--xml", action="store_true", help="emit Journal Reader XML")
    g.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--validate", action="store_true", help="parse and print structural counts")
    args = ap.parse_args(argv)
    data = open(args.file, "rb").read()
    doc = Document.parse(data)
    if args.xml:
        sys.stdout.write(document_xml(doc))
        return 0
    if args.json:
        json.dump(document_json(doc), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    def count(nodes):
        total = 0
        for n in nodes:
            total += len(n.ink_strokes) + count(n.children) + count(n.lines)
        return total
    strokes = sum(count(p.segment.content) for p in doc.pages if p.segment)
    print("file: %s" % args.file)
    print("signature: %s  version: %#x  pages: %d" % (
        doc.nb.signature.decode("latin1"), doc.nb.version, doc.nb.page_count))
    print("default page: %dx%d (1/100 mm)" % (doc.default_width, doc.default_height))
    print("stationery: %s" % ("present" if doc.stationery else "absent"))
    print("strokes decoded: %d" % strokes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
