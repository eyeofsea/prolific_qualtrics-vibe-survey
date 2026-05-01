"""Tests for lib.secrets — keyring wrapper for LLM API key."""

from __future__ import annotations

from unittest.mock import patch

from lib import secrets as sec


def test_set_and_get_roundtrip():
    fake_store: dict[tuple[str, str], str] = {}

    def fake_set(service, user, value):
        fake_store[(service, user)] = value

    def fake_get(service, user):
        return fake_store.get((service, user))

    with patch("lib.secrets.keyring.set_password", side_effect=fake_set), \
         patch("lib.secrets.keyring.get_password", side_effect=fake_get):
        sec.set_llm_api_key("sk-ant-xxx")
        assert sec.get_llm_api_key() == "sk-ant-xxx"


def test_get_returns_none_when_absent():
    with patch("lib.secrets.keyring.get_password", return_value=None):
        assert sec.get_llm_api_key() is None


def test_delete_swallows_password_delete_error():
    import keyring.errors

    def fake_del(service, user):
        raise keyring.errors.PasswordDeleteError("not found")

    with patch("lib.secrets.keyring.delete_password", side_effect=fake_del):
        sec.delete_llm_api_key()  # should not raise
