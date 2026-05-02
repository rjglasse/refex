#!/usr/bin/env python3
"""Extract academic references from PDF files using pdftotext + LLM repair."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

YEAR_PATTERN = re.compile(r"\((?:1[89]\d{2}|20\d{2}[a-z]?)\)")
DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+")
REFERENCE_HEADERS = [
    r"^\s*(?:references?|bibliography|works\s+cited|literature\s+cited)\s*$",
]


# ── extraction ───────────────────────────────────────────────────────────────

def extract_text(pdf_path: Path) -> str:
    """Extract text from PDF using pdftotext."""
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")
    text = result.stdout
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return text


def find_reference_section(text: str) -> str:
    """Locate the reference section and return everything after it."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for pattern in REFERENCE_HEADERS:
            if re.match(pattern, line, re.IGNORECASE):
                body = lines[i + 1:]
                while body and not body[0].strip():
                    body.pop(0)
                return "\n".join(body)

    # Fallback: use last 40% of document
    start = int(len(lines) * 0.6)
    return "\n".join(lines[start:])


def _has_numbered_refs(raw: str) -> bool:
    lines = raw.splitlines()
    return sum(1 for l in lines[:50] if re.search(r"\[\d+\]", l)) >= 5


def _split_numbered(raw: str) -> list[str]:
    refs: list[list[str]] = []
    current: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                refs.append(current)
                current = []
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

    if current and any(l.strip() for l in current):
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


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_reference(ref_text: str) -> dict:
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
    doi_match = DOI_PATTERN.search(ref_text)
    if doi_match:
        parts["doi"] = doi_match.group(0).rstrip(".")
    year_match = YEAR_PATTERN.search(ref_text)
    if year_match:
        parts["year"] = year_match.group(0).strip("()")
    volume_match = re.search(
        r"(\d+)\s*\(\d+\)\s*[,:]\s*(\d+[\-\u2013]\d+|\d+)", ref_text
    )
    if volume_match:
        parts["volume"] = volume_match.group(1)
        parts["pages"] = volume_match.group(2)
    author_match = re.match(r"^(.+?)\s*\(?\d{4}", ref_text)
    if author_match:
        authors_raw = author_match.group(1).strip()
        authors_raw = re.sub(r'[,"\']\s*$', "", authors_raw).strip()
        if len(authors_raw) < len(ref_text) * 0.7:
            parts["authors"] = authors_raw
    if parts["year"]:
        after_year = ref_text.split(parts["year"], 1)
        if len(after_year) > 1:
            remainder = after_year[1].strip().lstrip(".)]. ")
            title_match = re.match(r"(.+?)\.\s*[A-Z]", remainder)
            if title_match:
                parts["title"] = title_match.group(1).strip()
                rest = remainder[title_match.end() - 1:]
                journal_match = re.match(r"\.\s*(.+?)[,.]\s*\d", rest)
                if journal_match:
                    parts["journal"] = journal_match.group(1).strip()
    return parts


# ── LLM repair ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a reference repair assistant. You receive academic references extracted from PDFs that may contain extraction artifacts.

Common artifacts to detect and fix:
1. TRUNCATION: Reference ends mid-sentence or is missing venue/pages/DOI
2. COLUMN_BLEED: Garbled words from adjacent text columns leaked in
3. MANGLED: Hyphenation not rejoined, garbled characters, missing spaces
4. HEADER_NOISE: Page headers/numbers inserted mid-reference
5. MISSING_PARTS: No year, no title, no venue — too short to be valid
6. DUPLICATE: Same reference appears twice with slight differences

For each reference, return:
- "issues": list of issue codes (empty list if clean)
- "repaired": the fixed reference text (same as original if clean)
- "confidence": 0-1 how confident you are in the repair
- "summary": one-line description of what was done

Issue codes: TRUNCATED, COLUMN_BLEED, MANGLED, HEADER_NOISE, MISSING_PARTS, DUPLICATE, CLEAN

IMPORTANT: Preserve as much original text as possible. Remove only obvious artifacts. Never hallucinate missing bibliographic details — if you cannot repair confidently, set low confidence and note it."""


def _repair_batch(references: list[str], start_idx: int,
                  model: str) -> list[dict]:
    import openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    numbered = "\n".join(
        f"[{start_idx + i}] {ref}" for i, ref in enumerate(references)
    )
    user_prompt = f"""Analyze these references extracted from a PDF. For each, flag issues and provide a repaired version.

References:
{numbered}

Return a JSON array with one object per reference:
[{{"index": 0, "original": "...", "issues": ["TRUNCATED"], "repaired": "...", "confidence": 0.9, "summary": "..."}}]"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", content, re.DOTALL)
        result = json.loads(match.group()) if match else []

    if isinstance(result, dict):
        for key in ("references", "results", "repairs", "items"):
            if key in result and isinstance(result[key], list):
                result = result[key]
                break
        else:
            for v in result.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    result = v
                    break

    if not isinstance(result, list):
        return []

    return [r for r in result if isinstance(r, dict)]


def repair_references(references: list[str], model: str | None = None,
                      batch_size: int = 15) -> tuple[list[str], str]:
    """Repair references via LLM. Returns (repaired_refs, log_text)."""
    if not os.environ.get("OPENAI_API_KEY"):
        return references, "(repair skipped: OPENAI_API_KEY not set)\n"

    model = model or os.environ.get("PQBL_OPENAI_MODEL", "gpt-4.1-mini")

    all_results: list[dict] = []
    for batch_start in range(0, len(references), batch_size):
        batch = references[batch_start: batch_start + batch_size]
        all_results.extend(_repair_batch(batch, batch_start, model))

    # Fill gaps
    filled = []
    for i, ref in enumerate(references):
        match = next((r for r in all_results if r.get("index") == i), None)
        if match:
            filled.append(match)
        else:
            filled.append({
                "index": i, "original": ref, "issues": [],
                "repaired": ref, "confidence": 1.0,
                "summary": "Not processed",
            })

    # Build log
    log_lines = []
    issue_counts: dict[str, int] = {}
    fixed = 0
    for r in filled:
        issues = r.get("issues", [])
        if not issues or issues == ["CLEAN"]:
            continue
        fixed += 1
        for code in issues:
            issue_counts[code] = issue_counts.get(code, 0) + 1
        idx = r.get("index", "?")
        log_lines.append(f"--- Ref #{idx} ---")
        log_lines.append(f"  Issues: {', '.join(issues)}")
        log_lines.append(f"  Summary: {r.get('summary', '')}")
        log_lines.append(f"  Confidence: {r.get('confidence', 0):.0%}")
        orig = r.get("original", "")
        repd = r.get("repaired", "")
        if orig != repd:
            log_lines.append(f"  Before: {orig[:120]}{'...' if len(orig)>120 else ''}")
            log_lines.append(f"  After:  {repd[:120]}{'...' if len(repd)>120 else ''}")
        log_lines.append("")

    header = f"Repair report: {fixed}/{len(references)} references had issues\n"
    if issue_counts:
        header += "Issue breakdown: " + ", ".join(
            f"{k}={v}" for k, v in sorted(issue_counts.items())
        )
    log = header + "\n" + "\n".join(log_lines)

    repaired_refs = [r.get("repaired", r.get("original", "")) for r in filled]
    return repaired_refs, log


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract academic references from a PDF (pdftotext + optional LLM repair)."
    )
    parser.add_argument("pdf", type=Path, help="Path to the PDF file")
    parser.add_argument("--json", action="store_true",
                        help="Output parsed references as JSON")
    parser.add_argument("--repair", action="store_true",
                        help="Use LLM to detect and fix extraction artifacts")
    parser.add_argument("--repair-model", type=str, default=None,
                        help="OpenAI model (default: $PQBL_OPENAI_MODEL or gpt-4.1-mini)")
    parser.add_argument("--repair-log", type=Path, default=None,
                        help="Write repair log to file")
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    refs = extract_references(args.pdf)

    if args.repair:
        refs, log = repair_references(refs, model=args.repair_model)
        if args.repair_log:
            args.repair_log.write_text(log)
        else:
            print(log, file=sys.stderr)

    if args.json:
        parsed = [parse_reference(r) for r in refs]
        json.dump(parsed, sys.stdout, indent=2, ensure_ascii=False)
    else:
        for i, ref in enumerate(refs, 1):
            print(f"[{i}] {ref}\n")


if __name__ == "__main__":
    main()
