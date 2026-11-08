"""
TOON MCP Server Package
Token-Optimized Object Notation for efficient AI context management.
"""

__version__ = "1.0.0"

from .patterns import PatternDetector, SmartCompressionStrategy
from .toon_converter import (
    TOONConverter,
    convert_json_to_toon,
    convert_toon_to_json,
)

__all__ = [
    "TOONConverter",
    "convert_json_to_toon",
    "convert_toon_to_json",
    "PatternDetector",
    "SmartCompressionStrategy",
    "TOONMCPServer",
    "BracketedPasteStreamProcessor",
    "toonify_text",
]


def __getattr__(name: str):
    if name == "TOONMCPServer":
        from .server import TOONMCPServer

        return TOONMCPServer
    if name == "BracketedPasteStreamProcessor":
        from .paste_wrapper import BracketedPasteStreamProcessor

        return BracketedPasteStreamProcessor
    if name == "toonify_text":
        from .paste_wrapper import toonify_text

        return toonify_text
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
