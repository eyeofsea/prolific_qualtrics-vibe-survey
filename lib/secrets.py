"""OS-keyring wrapper for the LLM API key."""

from __future__ import annotations

import keyring
import keyring.errors

_SERVICE = "prolific_qualtrics_vibe_survey"
_USER = "llm_api_key"


def set_llm_api_key(key: str) -> None:
    keyring.set_password(_SERVICE, _USER, key)


def get_llm_api_key() -> str | None:
    return keyring.get_password(_SERVICE, _USER)


def delete_llm_api_key() -> None:
    try:
        keyring.delete_password(_SERVICE, _USER)
    except keyring.errors.PasswordDeleteError:
        pass
