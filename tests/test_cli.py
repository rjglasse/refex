from pathlib import Path

from refex import cli


def test_plain_text_output_does_not_duplicate_existing_bracket_label(
    capsys, monkeypatch, tmp_path
):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr("sys.argv", ["refex", str(pdf)])
    monkeypatch.setattr(
        cli,
        "extract_references",
        lambda path: ["[1] Existing numbered ref"],
    )

    cli.main()

    assert capsys.readouterr().out == "[1] Existing numbered ref\n\n"


def test_plain_text_output_adds_label_to_unnumbered_reference(
    capsys, monkeypatch, tmp_path
):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr("sys.argv", ["refex", str(pdf)])
    monkeypatch.setattr(
        cli,
        "extract_references",
        lambda path: ["Existing unnumbered ref"],
    )

    cli.main()

    assert capsys.readouterr().out == "[1] Existing unnumbered ref\n\n"


def test_plain_text_output_does_not_duplicate_existing_dot_label(
    capsys, monkeypatch, tmp_path
):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr("sys.argv", ["refex", str(pdf)])
    monkeypatch.setattr(
        cli,
        "extract_references",
        lambda path: ["1. Existing numbered ref"],
    )

    cli.main()

    assert capsys.readouterr().out == "1. Existing numbered ref\n\n"
