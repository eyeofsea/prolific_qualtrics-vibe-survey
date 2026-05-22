"""페이지 간 공유 키와 헬퍼. lib는 이 파일을 import 하지 않음."""

from __future__ import annotations

from typing import Any

import streamlit as st


COMPLETION_CODE = "completion_code"
STUDY_TITLE = "study_title"
EXPECTED_MINUTES = "expected_minutes"
PROLIFIC_API_KEY = "prolific_api_key"
QUALTRICS_SURVEY_ID = "qualtrics_survey_id"
QUALTRICS_SURVEY_NAME = "qualtrics_survey_name"


DEFAULTS: dict[str, Any] = {
    COMPLETION_CODE: "",
    STUDY_TITLE: "",
    EXPECTED_MINUTES: 8,
    PROLIFIC_API_KEY: None,
    QUALTRICS_SURVEY_ID: None,
    QUALTRICS_SURVEY_NAME: None,
}


def init() -> None:
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get(key: str, fallback: Any = None) -> Any:
    return st.session_state.get(key, fallback)


def set_(key: str, value: Any) -> None:
    st.session_state[key] = value
