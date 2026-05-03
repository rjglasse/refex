"""LLM-based reference repair logic."""

import json
import os
import re

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
- "parsed": (ONLY if requested) an object with keys: authors, year, title, journal, volume, pages, doi

Issue codes: TRUNCATED, COLUMN_BLEED, MANGLED, HEADER_NOISE, MISSING_PARTS, DUPLICATE, CLEAN

IMPORTANT: Preserve as much original text as possible. Remove only obvious artifacts. Never hallucinate missing bibliographic details — if you cannot repair confidently, set low confidence and note it."""


def _repair_batch(references: list[str], start_idx: int,
                  model: str, parse_json: bool = False) -> list[dict]:
    import openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    numbered = "\n".join(
        f"[{start_idx + i}] {ref}" for i, ref in enumerate(references)
    )
    
    parsed_instruction = ""
    if parse_json:
        parsed_instruction = '- "parsed": {"authors": "...", "year": "...", "title": "...", "journal": "...", "volume": "...", "pages": "...", "doi": "..."}'

    user_prompt = f"""Analyze these references extracted from a PDF. For each, flag issues and provide a repaired version.
{f'Also parse each reference into structured fields.' if parse_json else ''}

References:
{numbered}

Return a JSON array with one object per reference:
[{{
    "index": {start_idx},
    "original": "...",
    "issues": ["TRUNCATED"],
    "repaired": "...",
    "confidence": 0.9,
    "summary": "..."
    {f', {parsed_instruction}' if parse_json else ''}
}}]"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
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


def _normalize_repair_result(result: dict, batch_start: int,
                             batch_len: int) -> dict | None:
    idx = result.get("index")
    if not isinstance(idx, int):
        return None
    if batch_start <= idx < batch_start + batch_len:
        return result
    if 0 <= idx < batch_len:
        normalized = dict(result)
        normalized["index"] = batch_start + idx
        return normalized
    return None


def repair_references(references: list[str], model: str | None = None,
                      batch_size: int = 15, parse_json: bool = False) -> tuple[list[str], str, list[dict] | None]:
    """Repair references via LLM. Returns (repaired_refs, log_text, parsed_data)."""
    if not os.environ.get("OPENAI_API_KEY"):
        return references, "(repair skipped: OPENAI_API_KEY not set)\n", None

    model = model or os.environ.get("REFEX_OPENAI_MODEL", "gpt-4o-mini")

    all_results: list[dict] = []
    for batch_start in range(0, len(references), batch_size):
        batch = references[batch_start: batch_start + batch_size]
        batch_results = _repair_batch(batch, batch_start, model, parse_json=parse_json)
        all_results.extend(
            r for r in (
                _normalize_repair_result(result, batch_start, len(batch))
                for result in batch_results
            )
            if r is not None
        )

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
    parsed_data = None
    if parse_json:
        parsed_data = []
        for r in filled:
            p = r.get("parsed", {})
            p["raw"] = r.get("repaired", r.get("original", ""))
            parsed_data.append(p)
            
    return repaired_refs, log, parsed_data
