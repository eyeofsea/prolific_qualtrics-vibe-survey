"""Build a complete QSF dict from a SurveyInput. No template file required."""

from __future__ import annotations

import uuid

from lib.qsf import AttentionCheck, Question, Scale, SurveyInput


def _new_survey_id() -> str:
    return "SV_" + uuid.uuid4().hex[:14].upper()


def build_qsf(survey: SurveyInput) -> dict:
    survey_id = _new_survey_id()
    elements: list[dict] = [_build_survey_options(survey_id)]
    elements.append(_build_consent_sq(survey_id, survey.consent_text))
    for i, q in enumerate(survey.demographics, start=1):
        elements.append(_build_demo_sq(survey_id, q, i))
    for i, s in enumerate(survey.scales, start=1):
        elements.append(_build_scale_sq(survey_id, s, i))
    if survey.attention_check is not None:
        elements.append(_build_attention_sq(survey_id, survey.attention_check))
    elements.append(_build_end_sq(survey_id, survey.completion_code))
    return {
        "SurveyEntry": _build_survey_entry(survey_id, survey.title),
        "SurveyElements": elements,
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


def _build_survey_options(survey_id: str) -> dict:
    return {
        "SurveyID": survey_id,
        "Element": "SO",
        "PrimaryAttribute": "Survey Options",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": {
            "BackButton": "false",
            "SaveAndContinue": "true",
            "SurveyProtection": "PublicSurvey",
            "BallotBoxStuffingPrevention": "false",
            "NoIndex": "Yes",
            "SecureResponseFiles": "true",
            "SurveyExpiration": "None",
            "SurveyTermination": "DefaultMessage",
            "Header": "",
            "Footer": "",
            "ProgressBarDisplay": "VerboseText",
            "PartialData": "+1 week",
            "ValidationMessage": "",
            "PreviousButton": "",
            "NextButton": "",
            "SkinLibrary": "qualtrics",
            "SkinType": "MQ",
            "Skin": "qbase-fluid",
            "NewScoring": 1,
        },
    }


def _build_consent_sq(survey_id: str, consent_text: str) -> dict:
    return {
        "SurveyID": survey_id,
        "Element": "SQ",
        "PrimaryAttribute": "QID_CONSENT",
        "SecondaryAttribute": "Consent text",
        "TertiaryAttribute": None,
        "Payload": {
            "QuestionText": consent_text,
            "DataExportTag": "Q_CONSENT",
            "QuestionType": "DB",
            "Selector": "TB",
            "Configuration": {"QuestionDescriptionOption": "UseText"},
            "QuestionDescription": "Consent",
            "Validation": {"Settings": {"ForceResponse": "OFF", "Type": "None"}},
            "Language": [],
            "QuestionID": "QID_CONSENT",
        },
    }


def _question_type_to_qualtrics(qtype: str) -> tuple[str, str, str | None]:
    if qtype == "SingleChoice":
        return ("MC", "SAVR", "TX")
    if qtype == "MultiChoice":
        return ("MC", "MAVR", "TX")
    if qtype == "Text":
        return ("TE", "SL", None)
    raise ValueError(f"unknown demographics type: {qtype}")


def _build_demo_sq(survey_id: str, q: Question, idx: int) -> dict:
    qid = f"QID_DEMO_{idx}"
    qtype, selector, sub = _question_type_to_qualtrics(q.type)
    payload: dict = {
        "QuestionText": q.text,
        "DataExportTag": f"Q_DEMO_{idx}",
        "QuestionType": qtype,
        "Selector": selector,
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": q.text[:60],
        "Validation": {"Settings": {"ForceResponse": "ON", "Type": "None"}},
        "Language": [],
        "QuestionID": qid,
    }
    if sub is not None:
        payload["SubSelector"] = sub
    if q.choices:
        payload["Choices"] = {
            str(i + 1): {"Display": c} for i, c in enumerate(q.choices)
        }
        payload["ChoiceOrder"] = [str(i + 1) for i in range(len(q.choices))]
    return {
        "SurveyID": survey_id,
        "Element": "SQ",
        "PrimaryAttribute": qid,
        "SecondaryAttribute": q.text[:60],
        "TertiaryAttribute": None,
        "Payload": payload,
    }


LIKERT_7POINT = [
    "전혀 동의하지 않는다",
    "동의하지 않는다",
    "약간 동의하지 않는다",
    "보통이다",
    "약간 동의한다",
    "동의한다",
    "매우 동의한다",
]


def _build_scale_sq(survey_id: str, scale: Scale, idx: int) -> dict:
    qid = f"QID_SCALE_{idx}"
    n = len(scale.statements)
    invalid = [i for i in scale.reverse_indices if i < 1 or i > n]
    if invalid:
        raise ValueError(
            f"SCALE '{scale.name}' REVERSE index 범위 초과: {invalid} "
            f"(statements {n}개)"
        )
    payload: dict = {
        "QuestionText": "다음 진술에 동의하시는 정도를 표시해 주세요.",
        "DataExportTag": f"Q_SCALE_{idx}",
        "QuestionType": "Matrix",
        "Selector": "Likert",
        "SubSelector": "SingleAnswer",
        "Configuration": {
            "QuestionDescriptionOption": "UseText",
            "TextPosition": "inline",
            "ChoiceColumnWidth": 25,
            "RepeatHeaders": "none",
            "WhiteSpace": "ON",
            "MobileFirst": True,
        },
        "QuestionDescription": f"{scale.name} Scale",
        "Choices": {
            str(i + 1): {"Display": s} for i, s in enumerate(scale.statements)
        },
        "ChoiceOrder": [str(i + 1) for i in range(n)],
        "Answers": {
            str(i + 1): {"Display": LIKERT_7POINT[i]} for i in range(7)
        },
        "AnswerOrder": [str(i + 1) for i in range(7)],
        "ChoiceDataExportTags": False,
        "Validation": {"Settings": {"ForceResponse": "ON", "Type": "None"}},
        "Language": [],
        "QuestionID": qid,
    }
    if scale.reverse_indices:
        payload["RecodeValues"] = {
            str(i): str(8 - i) if i in scale.reverse_indices else str(i)
            for i in range(1, n + 1)
        }
    return {
        "SurveyID": survey_id,
        "Element": "SQ",
        "PrimaryAttribute": qid,
        "SecondaryAttribute": f"{scale.name} Matrix",
        "TertiaryAttribute": None,
        "Payload": payload,
    }


_ATTENTION_CHOICES = {
    "1": {"Display": "1 (전혀 동의하지 않는다)"},
    "2": {"Display": "2"},
    "3": {"Display": "3"},
    "4": {"Display": "4 (보통이다)"},
    "5": {"Display": "5 (약간 동의한다)"},
    "6": {"Display": "6"},
    "7": {"Display": "7 (매우 동의한다)"},
}


def _build_attention_sq(survey_id: str, attn: AttentionCheck) -> dict:
    return {
        "SurveyID": survey_id,
        "Element": "SQ",
        "PrimaryAttribute": "QID_ATTENTION",
        "SecondaryAttribute": "Attention check",
        "TertiaryAttribute": None,
        "Payload": {
            "QuestionText": attn.text,
            "DataExportTag": "Q_ATTENTION",
            "QuestionType": "MC",
            "Selector": "SAVR",
            "SubSelector": "TX",
            "Configuration": {"QuestionDescriptionOption": "UseText"},
            "QuestionDescription": "Attention check",
            "Choices": dict(_ATTENTION_CHOICES),
            "ChoiceOrder": [str(i) for i in range(1, 8)],
            "Validation": {"Settings": {"ForceResponse": "ON", "Type": "None"}},
            "Language": [],
            "QuestionID": "QID_ATTENTION",
            "AttentionExpected": attn.expected,
        },
    }


def _build_end_sq(survey_id: str, code: str) -> dict:
    text = (
        f"설문에 참여해 주셔서 감사합니다.\n\n"
        f"Prolific Completion Code: {code}\n\n"
        f"위 코드를 Prolific에 입력하셔야 보상이 지급됩니다."
    )
    return {
        "SurveyID": survey_id,
        "Element": "SQ",
        "PrimaryAttribute": "QID_END",
        "SecondaryAttribute": "End message",
        "TertiaryAttribute": None,
        "Payload": {
            "QuestionText": text,
            "DataExportTag": "Q_END",
            "QuestionType": "DB",
            "Selector": "TB",
            "Configuration": {"QuestionDescriptionOption": "UseText"},
            "QuestionDescription": "End",
            "Validation": {"Settings": {"ForceResponse": "OFF", "Type": "None"}},
            "Language": [],
            "QuestionID": "QID_END",
        },
    }
