"""Export a Document to the Journal Reader XML schema (reference-compatible)."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta

from .document import Document, Page
from .richink import Node, Segment
from .stationery import (Stationery, BG_STYLES, LINE_STYLES, TITLE_STYLES, DATE_STYLES,
                         IMAGE_STYLES, MARGIN_TYPES, color_hex)

NS = "urn:schemas-microsoft-com:tabletpc:journalreader"

HOSTED_TYPES = {
    "{29C4CC4F-5A37-4D53-9FE4-F74731B2D444}": "Text",
    "{A201ECB0-0C0A-4C81-84E4-D82614E2ACBA}": "Image",
    "{EBD73B02-79E6-4899-B70C-DD185CF4E26B}": "Flag",
}

DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
    "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y",
    "%d.%m.%Y %H:%M:%S", "%d.%m.%Y",
]


def _round(x: float) -> int:
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def _hm(x: float) -> int:
    return _round(x * 2540.0)


def _bounds_value(x: float) -> int:
    return _round(x * 2.54)


def _fmt_float(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return ("%.9f" % v).rstrip("0").rstrip(".")


def parse_date(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "0000-00-00T00:00:00"
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return "0000-00-00T00:00:00"


def stationery_xml(st: Stationery | None) -> str:
    if st is None:
        return ('<Stationery><Background Style="None"/>'
                '<Title Style="None" DateStyle="None">'
                '<TitleArea Left="0" Top="0" Width="0" Height="0"/></Title>'
                '<LineLayout><Horizontal Style="None"/><Vertical Style="None"/>'
                '<Margin Style="None"/></LineLayout></Stationery>')
    out = ["<Stationery>"]
    bg_style = BG_STYLES.get(st.bg_style, "")
    out.append('<Background Style="%s"' % bg_style)
    if st.bg_style != 0:
        out.append(' Color="%s"' % color_hex(st.bg_color))
    if st.image_name or st.image_data:
        out.append('><Image Style="%s" Fade="%d"><Path>%s</Path><Bitmap>%s</Bitmap></Image></Background>'
                   % (IMAGE_STYLES.get(st.image_style, ""), st.image_fade,
                      _esc(st.image_name), base64.b64encode(st.image_data).decode()))
    else:
        out.append("/>")
    title_style = TITLE_STYLES.get(st.title_style, "")
    date_style = DATE_STYLES.get(st.date_style, "")
    out.append('<Title Style="%s" DateStyle="%s"' % (title_style, date_style))
    if st.title_style != 0:
        out.append(' Color="%s"' % color_hex(st.title_color))
    left, top = _hm(st.title_left), _hm(st.title_top)
    right, bottom = _hm(st.title_right), _hm(st.title_bottom)
    out.append('><TitleArea Left="%d" Top="%d" Width="%d" Height="%d"/></Title>'
               % (left, top, right - left, bottom - top))
    out.append("<LineLayout>")
    out.append(_line_xml("Horizontal", st.h_style, st.h_color, st.h_before, st.h_between))
    out.append(_line_xml("Vertical", st.v_style, st.v_color, st.v_before, st.v_between))
    margin = '<Margin Style="%s"' % LINE_STYLES.get(st.margin_style, "")
    if st.margin_style != 0:
        margin += ' Color="%s" Type="%s" Spacing="%d"' % (
            color_hex(st.margin_color), MARGIN_TYPES.get(st.margin_type, ""), _hm(st.margin_spacing))
    out.append(margin + "/>")
    out.append("</LineLayout></Stationery>")
    return "".join(out)


def _line_xml(name, style, color, before, between):
    out = ['<%s Style="%s"' % (name, LINE_STYLES.get(style, ""))]
    if style != 0:
        out.append(' Color="%s" SpacingBefore="%d" SpacingBetween="%d"'
                   % (color_hex(color), _hm(before), _hm(between)))
    out.append("/>")
    return "".join(out)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _attrs(rect, present=True) -> str:
    if not present:
        return ""
    return ' Left="%d" Top="%d" Width="%d" Height="%d"' % (
        _bounds_value(rect.x), _bounds_value(rect.y),
        _bounds_value(rect.width), _bounds_value(rect.height))


def _transform_xml(t) -> str:
    if not t:
        return ""
    return "<ScalarTransform%s/>" % "".join(
        ' Mat%d="%s"' % (i + 1, _fmt_float(v)) for i, v in enumerate(t))


def node_xml(node: Node) -> str:
    kind = node.kind
    if kind == "GroupNode":
        inner = _transform_xml(node.transform) + "".join(node_xml(c) for c in node.children)
        head = "<GroupNode" + _attrs(node.rect)
        return head + (">" + inner + "</GroupNode>" if inner else "/>")
    if kind == "Reflow":
        return "<Reflow>" + "".join(node_xml(c) for c in node.children) + "</Reflow>"
    if kind in ("InkWord", "Drawing"):
        out = ["<%s%s>" % (kind, _attrs(node.rect))]
        out.append(_transform_xml(node.transform))
        if node.alternates:
            out.append("<AlternateList>" + "".join("<Alternate>%s</Alternate>" % _esc(a)
                                                    for a in node.alternates) + "</AlternateList>")
        if node.can_reclassify is not None:
            out.append("<CanReclassify>%s</CanReclassify>" % ("true" if node.can_reclassify else "false"))
        if node.ink_class:
            out.append("<InkClass>%s</InkClass>" % _esc(node.ink_class))
        if node.confidence is not None:
            out.append("<Confidence>%d</Confidence>" % node.confidence)
        if node.pinned is not None:
            out.append("<Pinned>%s</Pinned>" % ("1" if node.pinned else "0"))
        out.append("<InkObject>%s</InkObject>" % base64.b64encode(node.ink).decode())
        out.append("</%s>" % kind)
        return "".join(out)
    if kind == "Paragraph":
        out = ['<Paragraph BlockNumber="%d">' % node.block_number]
        for line in node.lines:
            out.append('<Line LineNumber="%d"%s>' % (line.line_number, _attrs(line.rect, line.has_rect)))
            out.append("".join(node_xml(c) for c in line.children))
            if line.metrics is not None:
                out.append(_metrics_xml(line.metrics))
            out.append("</Line>")
        out.append("</Paragraph>")
        return "".join(out)
    if kind == "HostedNode":
        out_kind = HOSTED_TYPES.get(node.guid, "HostedNode")
        if out_kind == "Text":
            return ("<Text%s>%s</Text>" % (_attrs(node.rect), _esc(node.text)))
        if out_kind in ("Image", "Flag"):
            return ("<%s%s>%s</%s>" % (out_kind, _attrs(node.rect),
                                       base64.b64encode(node.image).decode(), out_kind))
        return "<HostedNode%s/>" % _attrs(node.rect)
    return ""


def _metrics_xml(metrics: dict) -> str:
    out = ["<ParagraphLineMetrics>"]
    base = metrics.get("Baseline")
    if base is not None:
        out.append("<Baseline" + "".join(' %s="%s"' % (k, _esc(v)) for k, v in base.items()) + "/>")
    for name in ("Ascender", "Descender", "Midline"):
        if name in metrics:
            attrs = metrics[name]
            if isinstance(attrs, dict) and attrs:
                out.append("<%s%s/>" % (name, "".join(' %s="%s"' % (k, _esc(v)) for k, v in attrs.items())))
            else:
                out.append("<%s/>" % name)
    out.append("</ParagraphLineMetrics>")
    return "".join(out)


def page_xml(page: Page) -> str:
    seg = page.segment
    width = int(seg.width * 2.54) if seg else 0
    height = int(seg.height * 2.54) if seg else 0
    attrs = ' Number="%d" Width="%d" Height="%d"' % (page.number, width, height)
    if seg and seg.line_height:
        attrs += ' LineHeight="%d"' % int(seg.line_height * 2.54)
    if seg and seg.language_id:
        attrs += ' LanguageId="%d"' % seg.language_id
    out = ["<JournalPage%s>" % attrs]
    if page.ink is not None and page.ink.stationery is not None:
        out.append(stationery_xml(page.ink.stationery))
    out.append("<TitleInfo><Text>%s</Text><Date>%s</Date></TitleInfo>"
               % (_esc(page.ink.title_text if page.ink else ""),
                  parse_date(page.ink.date_text if page.ink else "")))
    if seg is not None:
        if seg.content:
            out.append('<Content Type="Normal">' + "".join(node_xml(n) for n in seg.content) + "</Content>")
        else:
            out.append('<Content Type="Normal"/>')
    out.append("</JournalPage>")
    return "".join(out)


def document_xml(doc: Document) -> str:
    out = ['<JournalDocument xmlns="%s" Version="1.0" DefaultPageWidth="%d" DefaultPageHeight="%d">'
           % (NS, doc.default_width, doc.default_height)]
    out.append(stationery_xml(doc.stationery))
    for page in doc.pages:
        out.append(page_xml(page))
    out.append("</JournalDocument>\r\n")
    return "".join(out)
