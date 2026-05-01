"""LLM provider abstraction (Anthropic + OpenAI).

Auto-detects provider from API-key prefix. Single public function:
    freeform_to_markdown(text, api_key, provider_override=None) -> str
"""

from __future__ import annotations

from typing import Callable, Literal, TypeVar

import anthropic
from openai import OpenAI

Provider = Literal["anthropic", "openai"]

_T = TypeVar("_T")


class LLMError(Exception):
    """LLM call failed (network, quota, parse, or unknown provider)."""


def detect_provider(api_key: str) -> Provider:
    if api_key.startswith("sk-ant-"):
        return "anthropic"
    if api_key.startswith("sk-"):
        return "openai"
    raise LLMError(
        "Unknown LLM provider for the supplied key. "
        "Anthropic keys start with 'sk-ant-', OpenAI keys with 'sk-'."
    )


_ANTHROPIC_MODEL = "claude-haiku-4-5"
_OPENAI_MODEL = "gpt-4.1-mini"

_SYSTEM_PROMPT = """You are a survey-design assistant. Convert the user's freeform Korean
or English description of a research survey into the EXACT markdown format below.
Output ONLY the markdown — no explanation, no code fences, no prose around it.

Format:
# SURVEY: <title>

## CONSENT
<one or more paragraphs of informed consent text, ≥100 chars>

## DEMOGRAPHICS
Q: <question>
TYPE: SingleChoice | MultiChoice | Text
- <choice>
- <choice>
(repeat blocks; TYPE: Text omits the dash list)

## SCALE: <name>
ANCHOR: <e.g. 7-point Likert (전혀 동의하지 않는다 ~ 매우 동의한다)>
- <statement>
- <statement> [REVERSE]
(repeat blocks)

## ATTENTION_CHECK
TEXT: <instruction>
EXPECTED: <integer>

## END
COMPLETION_CODE: <6+ char alphanumeric>

Hard constraints:
- Maximum 7 SCALE sections (8+ is a parse error). 최대 7개.
- Pick each scale's <name> freely to fit the survey topic — any short label
  works (any short label like AS, WBI, Resilience, MyScale, 회복탄력성, etc.).
  The name should be a meaningful abbreviation or term, not generic ("Scale1").
  임의의 짧은 레이블을 자유롭게 지정하세요.
- TYPE values must be exactly: SingleChoice, MultiChoice, or Text.
- Append [REVERSE] only on reverse-coded scale items.
- ATTENTION_CHECK is optional; omit it entirely if not requested.
- Default ANCHOR is "7-point Likert (전혀 동의하지 않는다 ~ 매우 동의한다)".
- Match the user's language (Korean or English) for question text.
- COMPLETION_CODE must be 6+ alphanumeric characters with no spaces.
"""


def _call_anthropic(api_key: str, user_text: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=4000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_text}],
    )
    parts = [block.text for block in msg.content if hasattr(block, "text")]
    text = "".join(parts).strip()
    if not text:
        raise LLMError("Anthropic returned an empty response.")
    return text


def _call_openai(api_key: str, user_text: str) -> str:
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=_OPENAI_MODEL,
        max_tokens=4000,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    content = resp.choices[0].message.content
    text = (content or "").strip()
    if not text:
        raise LLMError("OpenAI returned an empty response.")
    return text


def _with_retry(fn: Callable[..., _T], *args: object) -> _T:
    last_exc: Exception | None = None
    for _ in range(2):  # initial + 1 retry
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001
            last_exc = e
    raise LLMError(str(last_exc))


def freeform_to_markdown(
    text: str,
    api_key: str,
    provider_override: Provider | None = None,
) -> str:
    if not text or not text.strip():
        raise LLMError("입력 텍스트가 비어 있습니다.")
    provider = provider_override or detect_provider(api_key)
    if provider == "anthropic":
        return _with_retry(_call_anthropic, api_key, text)
    if provider == "openai":
        return _with_retry(_call_openai, api_key, text)
    raise LLMError(f"Provider '{provider}' not implemented.")
