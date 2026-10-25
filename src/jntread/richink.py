"""Parser for the RichInk segment XML stored in InkStream tag 0x2001."""
from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

NS = "urn:schemas-microsoft-com:tabletpc:richink"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _decode_ink(text: str | None) -> bytes:
    if not text:
        return b""
    text = text.strip()
    if text.startswith("base64:"):
        text = text[7:]
    try:
        return base64.b64decode(text, validate=False)
    except Exception:
        return b""


def _f(node, name, default=0.0):
    try:
        return float(node.get(name, default))
    except (TypeError, ValueError):
        return default


def _i(node, name, default=0):
    try:
        return int(float(node.get(name, default)))
    except (TypeError, ValueError):
        return default


@dataclass
class Rect:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class Node:
    kind: str
    rect: Rect = field(default_factory=Rect)
    transform: list[float] | None = None
    ink: bytes = b""
    ink_strokes: list = field(default_factory=list)
    ink_warnings: list = field(default_factory=list)
    can_reclassify: bool | None = None
    ink_class: str | None = None
    confidence: int | None = None
    pinned: bool | None = None
    alternates: list[str] = field(default_factory=list)
    # Paragraph
    block_number: int = 0
    line_number: int = 0
    lines: list["Node"] = field(default_factory=list)
    metrics: dict | None = None
    # HostedNode
    guid: str = ""
    text: str = ""
    image: bytes = b""
    children: list["Node"] = field(default_factory=list)
    raw_attrs: dict = field(default_factory=dict)
    has_rect: bool = False


@dataclass
class Segment:
    version: str = "1"
    width: int = 0
    height: int = 0
    line_height: int = 0
    emus_per_host_unit: float = 914.4
    language_id: int = 0
    content: list[Node] = field(default_factory=list)
    raw_xml: str = ""


def _rect(node):
    br = None
    for c in node:
        if _local(c.tag) == "BoundingRect":
            br = c
            break
    if br is None:
        return Rect(), False
    return Rect(_f(br, "X"), _f(br, "Y"), _f(br, "Width"), _f(br, "Height")), True


def _transform(node) -> list[float] | None:
    for c in node:
        if _local(c.tag) == "ScalarTransform":
            return [float(c.get("Mat%d" % i, 0) or 0) for i in range(1, 10)]
    return None


def parse_node(elem) -> Node:
    kind = _local(elem.tag)
    n = Node(kind=kind, raw_attrs=dict(elem.attrib))
    n.rect, n.has_rect = _rect(elem)
    n.transform = _transform(elem)
    try:
        n.block_number = int(elem.get("BlockNumber", 0))
    except (TypeError, ValueError):
        pass
    try:
        n.line_number = int(elem.get("LineNumber", 0))
    except (TypeError, ValueError):
        pass
    for c in elem:
        name = _local(c.tag)
        text = (c.text or "").strip()
        if name == "InkObject":
            n.ink = _decode_ink(c.text)
            try:
                from .isf import parse as parse_isf
                ink = parse_isf(n.ink)
                n.ink_strokes = ink.strokes
                n.ink_warnings = ink.warnings
            except Exception as exc:
                n.ink_warnings = [str(exc)]
        elif name == "CanReclassify":
            n.can_reclassify = text.lower() in ("true", "1")
        elif name == "InkClass":
            n.ink_class = text
        elif name == "Confidence":
            try:
                n.confidence = int(text)
            except ValueError:
                pass
        elif name == "Pinned":
            n.pinned = text.lower() in ("true", "1")
        elif name == "AlternateList":
            n.alternates = [(a.text or "").strip() for a in c if _local(a.tag) == "Alternate"]
        elif name == "BlockNumber":
            try: n.block_number = int(text)
            except ValueError: pass
        elif name == "LineNumber":
            try: n.line_number = int(text)
            except ValueError: pass
        elif name == "Line":
            n.lines.append(parse_node(c))
        elif name == "ParagraphLineMetrics":
            m = {}
            for mc in c:
                mn = _local(mc.tag)
                if mn == "Baseline":
                    m[mn] = {k: v for k, v in mc.attrib.items()}
                else:
                    m[mn] = dict(mc.attrib)
            n.metrics = m
        elif name == "Guid":
            n.guid = text
        elif name == "HostedContent":
            for hc in c:
                hn = _local(hc.tag)
                if hn == "Text":
                    n.text = (hc.text or "")
                elif hn == "Image":
                    n.image = _decode_ink(hc.text)
        elif name == "HostedBoundingRect":
            n.raw_attrs["HostedBoundingRect"] = dict(c.attrib)
        elif name in ("Content", "GroupNode", "Paragraph", "InkWord", "Drawing", "Reflow", "HostedNode"):
            if name == "Content":
                n.children.extend(parse_node(x) for x in c)
            else:
                n.children.append(parse_node(c))
    return n


def parse(xml_text: str) -> Segment:
    elem = ET.fromstring(xml_text)
    if _local(elem.tag) != "InkSegment":
        raise ValueError("not an InkSegment document")
    seg = Segment(raw_xml=xml_text)
    for c in elem:
        name = _local(c.tag)
        text = (c.text or "").strip()
        if name == "Version":
            seg.version = text
        elif name == "SegmentWidth":
            seg.width = int(float(text))
        elif name == "SegmentHeight":
            seg.height = int(float(text))
        elif name == "SegmentLineHeight":
            seg.line_height = int(float(text))
        elif name == "EmusPerHostUnit":
            seg.emus_per_host_unit = float(text)
        elif name == "LanguageID":
            seg.language_id = int(float(text))
        elif name == "Content":
            seg.content.extend(parse_node(x) for x in c)
        elif name in ("GroupNode", "Paragraph", "InkWord", "Drawing", "Reflow", "HostedNode"):
            seg.content.append(parse_node(c))
    return seg
