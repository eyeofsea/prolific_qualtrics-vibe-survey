"""Tests for lib.llm."""

from __future__ import annotations

import pytest

from lib.llm import LLMError, detect_provider


def test_detect_anthropic_from_prefix():
    assert detect_provider("sk-ant-abc123") == "anthropic"


def test_detect_openai_from_prefix():
    assert detect_provider("sk-proj-xyz") == "openai"
    assert detect_provider("sk-abc123") == "openai"


def test_detect_unknown_raises():
    with pytest.raises(LLMError, match="provider"):
        detect_provider("invalid-key-format")


from unittest.mock import MagicMock, patch

from lib.llm import freeform_to_markdown


def test_anthropic_freeform_call_returns_markdown():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="# SURVEY: 회복탄력성\n\n## CONSENT\n...")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("lib.llm.anthropic.Anthropic", return_value=mock_client):
        out = freeform_to_markdown(
            "회복탄력성에 대한 7점 척도 5문항 설문 만들어줘.",
            api_key="sk-ant-test",
        )

    assert out.startswith("# SURVEY:")
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5"
    assert call_kwargs["max_tokens"] >= 2000
    system = call_kwargs["system"]
    assert "# SURVEY:" in system
    assert "최대 7" in system  # max-7 constraint
    assert "임의" in system or "freely" in system or "any short label" in system  # name freedom


def test_freeform_empty_input_raises():
    with pytest.raises(LLMError, match="비어"):
        freeform_to_markdown("   ", api_key="sk-ant-test")
