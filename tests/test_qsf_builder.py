"""Tests for lib/qsf_builder.build_qsf."""

from __future__ import annotations

import pytest

from lib.qsf import (
    AttentionCheck,
    Question,
    Scale,
    SurveyInput,
)
from lib.qsf_builder import build_qsf


def _minimal_survey() -> SurveyInput:
    return SurveyInput(
        title="테스트 설문",
        consent_text="이 연구는 X를 조사합니다. " * 10,
        demographics=[],
        scales=[],
        attention_check=None,
        completion_code="ABC12345",
    )


def test_survey_entry_has_title_and_language():
    qsf = build_qsf(_minimal_survey())
    entry = qsf["SurveyEntry"]
    assert entry["SurveyName"] == "테스트 설문"
    assert entry["SurveyLanguage"] == "KO"
    assert entry["SurveyID"].startswith("SV_")


def test_top_level_keys():
    qsf = build_qsf(_minimal_survey())
    assert set(qsf.keys()) == {"SurveyEntry", "SurveyElements"}
    assert isinstance(qsf["SurveyElements"], list)
