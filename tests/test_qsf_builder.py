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


def _find_element(qsf: dict, element: str, primary: str) -> dict | None:
    for el in qsf["SurveyElements"]:
        if el.get("Element") == element and el.get("PrimaryAttribute") == primary:
            return el
    return None


def test_survey_options_present():
    qsf = build_qsf(_minimal_survey())
    so = _find_element(qsf, "SO", "Survey Options")
    assert so is not None
    payload = so["Payload"]
    assert payload["SurveyProtection"] == "PublicSurvey"
    assert payload["BackButton"] == "false"
    assert payload["NoIndex"] == "Yes"


def test_consent_question_present():
    survey = _minimal_survey().model_copy(update={"consent_text": "본 연구의 목적은 ..."})
    qsf = build_qsf(survey)
    consent = next(
        (e for e in qsf["SurveyElements"]
         if e.get("Element") == "SQ" and e.get("PrimaryAttribute") == "QID_CONSENT"),
        None,
    )
    assert consent is not None
    assert consent["Payload"]["QuestionType"] == "DB"
    assert consent["Payload"]["QuestionText"] == "본 연구의 목적은 ..."
    assert consent["Payload"]["DataExportTag"] == "Q_CONSENT"
