import pytest
from refex.parser import parse_reference

def test_parse_reference_apa():
    ref = "Smith, J., & Doe, A. (2020). Title of the Paper. Journal of Testing, 10(2), 100-120. 10.1234/5678"
    parsed = parse_reference(ref)
    assert parsed["authors"] == "Smith, J., & Doe, A."
    assert parsed["year"] == "2020"
    assert parsed["title"] == "Title of the Paper"
    assert parsed["journal"] == "Journal of Testing"
    assert parsed["volume"] == "10"
    assert parsed["pages"] == "100-120"
    assert parsed["doi"] == "10.1234/5678"

def test_parse_reference_numbered():
    ref = "[1] Bloggs, J. (2021). Another Paper. 10.1109/ICSE.2021.00001"
    parsed = parse_reference(ref)
    assert parsed["authors"] == "Bloggs, J."
    assert parsed["year"] == "2021"
    assert parsed["title"] == "Another Paper"
    assert parsed["doi"] == "10.1109/ICSE.2021.00001"


def test_parse_reference_year_not_confused_by_early_occurrence():
    # "2020" appears in the author surname; the correct year is the parenthesised one.
    # The old string-split approach would cut at the first "2020" (inside the name).
    ref = "Wang2020, P. (2020). Deep Learning Survey. Neural Networks, 5(1), 1-15."
    parsed = parse_reference(ref)
    assert parsed["year"] == "2020"
    # Title must not contain the author fragment
    assert parsed["title"] is not None
    assert "Wang2020" not in (parsed["title"] or "")


def test_parse_reference_year_in_journal_name():
    # Year string appears in journal volume info but the publication year comes first.
    ref = "Zhang, L. (2019). Automated Testing. IEEE Trans. 2019(3), 45-60."
    parsed = parse_reference(ref)
    assert parsed["year"] == "2019"
    assert parsed["title"] is not None
