"""Command-line interface for refex."""

import argparse
import json
import re
import sys
from pathlib import Path

from .extractor import extract_references
from .parser import parse_reference
from .repairer import repair_references


REFERENCE_LABEL_PATTERN = re.compile(r"^\s*(?:\[\d+\]|\d+\.)\s+")


def _format_reference(index: int, ref: str) -> str:
    """Add a display index unless the reference already has one."""
    if REFERENCE_LABEL_PATTERN.match(ref):
        return ref
    return f"[{index}] {ref}"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="refex",
        description="Extract academic references from a PDF (pdftotext + optional LLM repair)."
    )
    parser.add_argument("pdf", type=Path, help="Path to the PDF file")
    parser.add_argument("--json", action="store_true",
                        help="Output parsed references as JSON")
    parser.add_argument("--repair", action="store_true",
                        help="Use LLM to detect and fix extraction artifacts")
    parser.add_argument("--repair-model", type=str, default=None,
                        help="OpenAI model (default: $REFEX_OPENAI_MODEL or gpt-4o-mini)")
    parser.add_argument("--repair-log", type=Path, default=None,
                        help="Write repair log to file")
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    try:
        refs = extract_references(args.pdf)
        parsed = None

        if args.repair:
            # If both --repair and --json are set, let the LLM do the parsing
            refs, log, parsed = repair_references(
                refs, model=args.repair_model, parse_json=args.json
            )
            if args.repair_log:
                args.repair_log.write_text(log)
            else:
                print(log, file=sys.stderr)

        if args.json:
            if not parsed:
                parsed = [parse_reference(r) for r in refs]
            json.dump(parsed, sys.stdout, indent=2, ensure_ascii=False)
        else:
            for i, ref in enumerate(refs, 1):
                print(f"{_format_reference(i, ref)}\n")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
