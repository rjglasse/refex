import pytest
import os
import json
from refex.repairer import repair_references

def test_repair_references_no_api_key(mocker):
    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    refs = ["Ref 1"]
    repaired, log, parsed = repair_references(refs)
    assert repaired == refs
    assert "repair skipped" in log
    assert parsed is None

def test_repair_references_with_mock_llm(mocker):
    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"})
    mock_client = mocker.patch("openai.OpenAI")
    
    # Mock response for _repair_batch
    mock_completion = mocker.Mock()
    mock_completion.message.content = json.dumps([
        {
            "index": 0,
            "original": "Ref 1",
            "issues": ["MANGLED"],
            "repaired": "Ref 1 (Fixed)",
            "confidence": 0.9,
            "summary": "Fixed something"
        }
    ])
    mock_client.return_value.chat.completions.create.return_value.choices = [mock_completion]
    
    refs = ["Ref 1"]
    repaired, log, parsed = repair_references(refs)
    
    assert repaired == ["Ref 1 (Fixed)"]
    assert "Ref 1 (Fixed)" in log
    assert parsed is None

def test_repair_references_unified_parsing(mocker):
    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"})
    mock_client = mocker.patch("openai.OpenAI")

    mock_completion = mocker.Mock()
    mock_completion.message.content = json.dumps([
        {
            "index": 0,
            "original": "Ref 1",
            "issues": ["CLEAN"],
            "repaired": "Ref 1 (Fixed)",
            "confidence": 0.9,
            "summary": "Fixed and parsed",
            "parsed": {
                "authors": "Author A",
                "year": "2020",
                "title": "Title A"
            }
        }
    ])
    mock_client.return_value.chat.completions.create.return_value.choices = [mock_completion]

    refs = ["Ref 1"]
    repaired, log, parsed = repair_references(refs, parse_json=True)

    assert repaired == ["Ref 1 (Fixed)"]
    assert parsed[0]["authors"] == "Author A"
    assert parsed[0]["raw"] == "Ref 1 (Fixed)"


def test_response_format_always_json(mocker):
    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"})
    mock_client = mocker.patch("openai.OpenAI")

    mock_completion = mocker.Mock()
    mock_completion.message.content = json.dumps([
        {"index": 0, "original": "Ref 1", "issues": [], "repaired": "Ref 1",
         "confidence": 1.0, "summary": "CLEAN"}
    ])
    mock_client.return_value.chat.completions.create.return_value.choices = [mock_completion]

    repair_references(["Ref 1"], model="some-future-model-xyz")

    call_kwargs = mock_client.return_value.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert "temperature" not in call_kwargs
