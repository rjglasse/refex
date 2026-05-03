"""Extract academic references from PDF files using pdftotext + LLM repair."""

from .extractor import extract_references
from .parser import parse_reference
from .repairer import repair_references
from .cli import main

__all__ = [
    "extract_references",
    "parse_reference",
    "repair_references",
    "main",
]
