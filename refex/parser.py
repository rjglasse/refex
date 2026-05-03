"""Regex-based reference parsing logic."""

import re

YEAR_PATTERN = re.compile(r"\(?(?:1[89]\d{2}|20\d{2}[a-z]?)\)?")
YEAR_VALUE_PATTERN = re.compile(r"^(?:1[89]\d{2}|20\d{2}[a-z]?)$")
DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+")

# Maximum fraction of the full reference string the author segment may occupy.
# References where the author string exceeds this ratio likely have a parsing error.
MAX_AUTHOR_RATIO = 0.7


def parse_reference(ref_text: str) -> dict:
    """Parse a reference string into structured parts using regex."""
    parts: dict[str, str | None] = {
        "raw": ref_text,
        "authors": None,
        "year": None,
        "title": None,
        "journal": None,
        "volume": None,
        "pages": None,
        "doi": None,
    }
    clean_ref = re.sub(r"^\s*(?:\[\d+\]|\d+\.)\s*", "", ref_text).strip()

    doi_match = DOI_PATTERN.search(clean_ref)
    if doi_match:
        parts["doi"] = doi_match.group(0).rstrip(".")
        # Remove DOI from clean_ref to avoid it being parsed as title/journal
        clean_ref = clean_ref.replace(doi_match.group(0), "").strip()
        
    year_match = YEAR_PATTERN.search(clean_ref)
    if year_match:
        year = year_match.group(0).strip("()")
        if YEAR_VALUE_PATTERN.match(year):
            parts["year"] = year
    volume_match = re.search(
        r"(\d+)\s*\(\d+\)\s*[,:]\s*(\d+[\-\u2013]\d+|\d+)", clean_ref
    )
    if volume_match:
        parts["volume"] = volume_match.group(1)
        parts["pages"] = volume_match.group(2)
    author_match = re.match(r"^(.+?)\s*\(?\d{4}", clean_ref)
    if author_match:
        authors_raw = author_match.group(1).strip()
        authors_raw = re.sub(r'[,"\']\s*$', "", authors_raw).strip()
        if len(authors_raw) < len(clean_ref) * MAX_AUTHOR_RATIO:
            parts["authors"] = authors_raw
    if parts["year"] and year_match:
        remainder = clean_ref[year_match.end():].strip().lstrip(".)]. ")
        title_match = re.match(r"(.+?)\.\s+([A-Z].*)", remainder)
        if title_match:
            parts["title"] = title_match.group(1).strip()
            rest = title_match.group(2)
            journal_match = re.match(r"(.+?)[,.]\s+\d", rest)
            if journal_match:
                parts["journal"] = journal_match.group(1).strip()
            elif rest:
                parts["journal"] = rest.rstrip(".").strip()
        else:
            parts["title"] = remainder.rstrip(".").strip()
    return parts
