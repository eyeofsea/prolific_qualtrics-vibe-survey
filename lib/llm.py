"""LLM provider abstraction (Anthropic + OpenAI).

Auto-detects provider from API-key prefix. Single public function:
    freeform_to_markdown(text, api_key, provider_override=None) -> str
"""

from __future__ import annotations

from typing import Literal

Provider = Literal["anthropic", "openai"]


class LLMError(Exception):
    """LLM call failed (network, quota, parse, or unknown provider)."""


def detect_provider(api_key: str) -> Provider:
    if api_key.startswith("sk-ant-"):
        return "anthropic"
    if api_key.startswith("sk-"):
        return "openai"
    raise LLMError(
        f"Unknown LLM provider for key starting with '{api_key[:8]}...'. "
        "Anthropic keys start with 'sk-ant-', OpenAI keys with 'sk-'."
    )
