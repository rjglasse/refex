# refex

Extract academic references from PDF files using `pdftotext` with optional LLM repair via OpenAI.

## Installation

```bash
pip install .
# or editable:
pip install -e .
```

Requires `pdftotext` (from poppler) on your PATH.

## Usage

### CLI

```bash
# Basic extraction
refex paper.pdf

# JSON output
refex paper.pdf --json

# With LLM repair (requires OPENAI_API_KEY)
refex paper.pdf --repair

# Custom model
refex paper.pdf --repair --repair-model gpt-4.1
```

### Python

```python
from refex import extract_references, repair_references, parse_reference

refs = extract_references("paper.pdf")
refs, _ = repair_references(refs)    # optional: LLM repair (needs OPENAI_API_KEY)

for ref in refs:
    parsed = parse_reference(ref)
    print(parsed["authors"], parsed["year"], parsed["title"])
```

## License

MIT

## Output format

**Default** — numbered references:

```
[1] Author, A. (2020). Title of paper. Journal Name, 10(2), 100-120.

[2] Author, B. (2021). Another title. Another Journal, 5(1), 50-60.
```

**`--json`** — structured JSON array:

```json
[
  {
    "raw": "Author, A. (2020). Title of paper. Journal Name, 10(2), 100-120.",
    "authors": "Author, A.",
    "year": "2020",
    "title": "Title of paper",
    "journal": "Journal Name",
    "volume": "10",
    "pages": "100-120",
    "doi": "10.1234/abc.123"
  }
]
```
