#!/usr/bin/env python3
"""Validate pdftotext reference extraction against expected counts and gold standards."""

import csv
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refex import extract_references

PDF_DIR = Path(__file__).resolve().parent / "pdfs"
EXPECTED_CSV = PDF_DIR / "expected-refs.csv"
GOLD_JSONL = PDF_DIR / "expected-references.jsonl"


def load_expected() -> dict[str, int]:
    counts = {}
    with open(EXPECTED_CSV) as f:
        for row in csv.reader(f):
            if row:
                counts[row[0].strip()] = int(row[1].strip())
    return counts


def load_gold(filename: str) -> list[str] | None:
    with open(GOLD_JSONL) as f:
        for line in f:
            data = json.loads(line)
            if data["filename"] == filename:
                return data["references"]
    return None


def fuzzy_match(extracted: str, gold: str) -> float:
    ex = re.sub(r"^\[\d+\]\s*", "", extracted).lower()
    gd = re.sub(r"^\[\d+\]\s*", "", gold).lower()
    ex_words = set(re.findall(r"[a-z0-9]+", ex))
    gd_words = set(re.findall(r"[a-z0-9]+", gd))
    if not gd_words:
        return 0.0
    return len(ex_words & gd_words) / len(gd_words)


def evaluate(expected: dict[str, int]) -> dict:
    results = {"total_found": 0, "total_expected": 0, "pdfs": {}}

    for filename, expected_count in expected.items():
        pdf_path = PDF_DIR / filename
        if not pdf_path.exists():
            continue

        t0 = time.time()
        try:
            refs = extract_references(pdf_path)
        except Exception as e:
            results["pdfs"][filename] = {"found": 0, "expected": expected_count,
                                          "error": str(e), "time": 0}
            continue
        elapsed = time.time() - t0

        found = len(refs)
        results["total_found"] += found
        results["total_expected"] += expected_count

        pdf_result = {
            "found": found,
            "expected": expected_count,
            "accuracy": found / expected_count if expected_count else 0,
            "time": elapsed,
        }

        gold = load_gold(filename)
        if gold:
            scores = []
            for gr in gold:
                best = max((fuzzy_match(er, gr) for er in refs), default=0)
                scores.append(best)
            pdf_result["avg_match"] = sum(scores) / len(scores) if scores else 0

        results["pdfs"][filename] = pdf_result

    results["overall_accuracy"] = (
        results["total_found"] / results["total_expected"]
        if results["total_expected"] else 0
    )
    return results


def main():
    expected = load_expected()
    results = evaluate(expected)

    print(f"{'PDF':<10} {'found':>6} {'expected':>9} {'match':>7}  {'time':>6}")
    print("-" * 45)
    for filename in sorted(expected):
        pr = results["pdfs"].get(filename, {})
        found = pr.get("found", "ERR")
        exp = pr.get("expected", "?")
        match = f"{pr.get('avg_match', 0):.0%}" if "avg_match" in pr else "N/A"
        t = f"{pr.get('time', 0):.2f}s"
        print(f"{filename:<10} {str(found):>6} {str(exp):>9} {match:>7}  {t:>6}")

    total = f"{results['total_found']}/{results['total_expected']}"
    print(f"\nTotal: {total} ({results['overall_accuracy']:.0%})")


if __name__ == "__main__":
    main()
