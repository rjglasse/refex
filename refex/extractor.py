"""PDF text extraction and reference splitting logic."""

import re
import subprocess
from pathlib import Path

from .parser import DOI_PATTERN

REFERENCE_HEADERS = [
    r"^\s*(?:references?|bibliography|works\s+cited|literature\s+cited)\s*$",
]


def extract_text(pdf_path: Path) -> str:
    """Extract text from PDF using pdftotext."""
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")
    text = result.stdout
    # Rejoin hyphenated words across lines
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return text


def find_reference_section(text: str) -> str:
    """Locate the reference section and return everything after it."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for pattern in REFERENCE_HEADERS:
            if re.match(pattern, line, re.IGNORECASE):
                body = lines[i + 1:]
                start = next((j for j, ln in enumerate(body) if ln.strip()), len(body))
                return "\n".join(body[start:])

    # Fallback: use last 40% of document
    start = int(len(lines) * 0.6)
    return "\n".join(lines[start:])


def _has_numbered_refs(raw: str) -> bool:
    lines = raw.splitlines()
    return sum(1 for line in lines[:50] if re.search(r"\[\d+\]", line)) >= 5


def _split_numbered(raw: str) -> list[str]:
    refs: list[list[str]] = []
    current: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\[(\d+)\]\s", stripped):
            if current:
                refs.append(current)
            current = [stripped]
        elif current:
            current.append(stripped)

    if current:
        refs.append(current)
    return [" ".join(r).strip() for r in refs if r]


def _is_ref_start(line: str) -> bool:
    if not line.strip():
        return False
    if re.match(r"^\s*\[\d+\]", line):
        return True
    if re.match(r"^\s*\d+\.\s", line):
        return True
    if re.match(r"^\s*[A-Z][a-z]+,\s+[A-Z]\.", line):
        return True
    if re.match(r"^\s*[A-Z][a-z]+,\s+[A-Z]\s*\.?\s", line):
        return True
    if re.match(r"^\s*[A-Z][A-Za-z]+\s*\(\d{4}\)", line):
        return True
    if re.match(r"^\s*[A-Z][a-z]+\s*\(\d{4}[a-z]?\)", line):
        return True
    if re.match(r"^\s*[A-Z][a-z]+\s+[A-Z][a-z]+\s*\(\d{4}[a-z]?\)", line):
        return True
    if DOI_PATTERN.match(line.strip()):
        return True
    return False


def _split_unnumbered(raw: str) -> list[str]:
    refs: list[list[str]] = []
    current: list[str] = []
    running_header = re.compile(
        r"^[A-Z][a-z]*\.?\s+[A-Z]\.\s+[A-Z][a-z]+\s+et\s+al\.?$"
    )
    noise = re.compile(r"^\d+\s+$|^\d+\s*\|\s*Page\s*\d+\s*of\s*\d+$|^1\s+3$")

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                refs.append(current)
                current = []
            continue
        if noise.match(stripped) or running_header.match(stripped):
            continue

        if not current:
            if _is_ref_start(stripped):
                current.append(stripped)
        elif _is_ref_start(stripped):
            refs.append(current)
            current = [stripped]
        else:
            current.append(stripped)

    if current and any(line.strip() for line in current):
        refs.append(current)

    results = []
    for r in refs:
        joined = re.sub(r"\s+", " ", " ".join(r)).strip()
        if joined and len(joined) > 20:
            results.append(joined)
    return results


def extract_references(pdf_path: Path) -> list[str]:
    text = extract_text(pdf_path)
    raw = find_reference_section(text)
    if _has_numbered_refs(raw):
        return _split_numbered(raw)
    return _split_unnumbered(raw)
