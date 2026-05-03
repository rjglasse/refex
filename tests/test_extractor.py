import pytest
from pathlib import Path
from refex.extractor import extract_text, find_reference_section, _is_ref_start, extract_references

PDF_DIR = Path(__file__).resolve().parent.parent / "pdfs"

def test_extract_text(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "Sample text with hyphenated-\nword."
    
    result = extract_text(Path("test.pdf"))
    assert result == "Sample text with hyphenatedword."
    mock_run.assert_called_once_with(
        ["pdftotext", "test.pdf", "-"],
        capture_output=True, text=True, timeout=30
    )

def test_find_reference_section():
    text = "Some body text\nReferences\n[1] Ref 1\n[2] Ref 2"
    assert find_reference_section(text) == "[1] Ref 1\n[2] Ref 2"
    
    text = "No header here\nJust some text"
    # Fallback uses last 40%
    # lines = 2, start = 1 (2 * 0.6)
    assert find_reference_section(text) == "Just some text"

def test_is_ref_start():
    assert _is_ref_start("[1] Smith et al.")
    assert _is_ref_start("1. Jones et al.")
    assert _is_ref_start("Smith, J. (2020)")
    assert _is_ref_start("10.1145/123456")
    assert not _is_ref_start("This is just a sentence.")

def test_extract_references(mocker):
    mocker.patch("refex.extractor.extract_text", return_value="References\n[1] Ref 1\n[2] Ref 2\n[3] Ref 3\n[4] Ref 4\n[5] Ref 5")
    # _has_numbered_refs will be True because it sees 5 [d+]
    refs = extract_references(Path("test.pdf"))
    assert len(refs) == 5
    assert refs[0] == "[1] Ref 1"


def test_doi_pattern_is_shared():
    from refex.extractor import DOI_PATTERN as extractor_doi
    from refex.parser import DOI_PATTERN as parser_doi
    assert extractor_doi is parser_doi


def test_is_ref_start_doi_line():
    assert _is_ref_start("10.1145/3491102.3501994 Smith et al.")


@pytest.mark.skipif(not (PDF_DIR / "001.pdf").exists(), reason="test PDFs not present")
def test_integration_extract_references_001():
    refs = extract_references(PDF_DIR / "001.pdf")
    assert len(refs) >= 1
    for ref in refs:
        assert isinstance(ref, str)
        assert len(ref) > 20
