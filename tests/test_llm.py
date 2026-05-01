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
