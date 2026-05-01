"""Build a complete QSF dict from a SurveyInput. No template file required."""

from __future__ import annotations

import uuid

from lib.qsf import SurveyInput


def _new_survey_id() -> str:
    return "SV_" + uuid.uuid4().hex[:14].upper()


def build_qsf(survey: SurveyInput) -> dict:
    survey_id = _new_survey_id()
    return {
        "SurveyEntry": _build_survey_entry(survey_id, survey.title),
        "SurveyElements": [],
    }


def _build_survey_entry(survey_id: str, title: str) -> dict:
    return {
        "SurveyID": survey_id,
        "SurveyName": title,
        "SurveyDescription": None,
        "SurveyOwnerID": "UR_GENERATED",
        "SurveyBrandID": "generated",
        "DivisionID": None,
        "SurveyLanguage": "KO",
        "SurveyActiveResponseSet": "RS_GENERATED",
        "SurveyStatus": "Inactive",
        "SurveyStartDate": "0000-00-00 00:00:00",
        "SurveyExpirationDate": "0000-00-00 00:00:00",
        "SurveyCreationDate": "2024-01-01 00:00:00",
        "CreatorID": "UR_GENERATED",
        "LastModified": "2024-01-01 00:00:00",
        "LastAccessed": "0000-00-00 00:00:00",
        "LastActivated": "0000-00-00 00:00:00",
        "Deleted": None,
    }
