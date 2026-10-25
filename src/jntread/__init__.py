"""Windows Journal (.jnt/.jtp) reader."""
from .document import Document, Page
from .nbtiff import NBDocument
from .cfb import CFB
from .richink import parse as parse_richink
from .isf import parse as parse_isf

__all__ = ["Document", "Page", "NBDocument", "CFB", "parse_richink", "parse_isf"]
__version__ = "1.0.0"
