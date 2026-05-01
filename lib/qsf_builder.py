"""Build a complete QSF dict from a SurveyInput. No template file required.

The output mirrors what Qualtrics itself emits: SurveyElements include not only
BL/FL/SO/SQ but also RS (response set), PROJ (project), SCO (scoring), STAT
(statistics) and QC (question count). Block payload is a dict keyed by string
indices ("0", "1", ...) — Qualtrics rejects list-shaped block payloads on import.
ChoiceOrder/AnswerOrder use integers; questions carry the bookkeeping fields
(DataVisibility, DefaultChoices, GradingData, NextChoiceId, NextAnswerId) that
Qualtrics writes on every export.
"""

from __future__ import annotations

import uuid

from lib.qsf import AttentionCheck, Question, Scale, SurveyInput


def _new_survey_id() -> str:
    return "SV_" + uuid.uuid4().hex[:14]


def _new_response_set_id() -> str:
    return "RS_" + uuid.uuid4().hex[:14]


def build_qsf(survey: SurveyInput) -> dict:
    survey_id = _new_survey_id()
    rs_id = _new_response_set_id()
    elements: list[dict] = [
        _build_blocks(survey_id, survey),
        _build_flow(survey_id, survey),
        _build_response_set(survey_id, rs_id),
        _build_question_count(survey_id),
        _build_survey_options(survey_id),
        _build_survey_statistics(survey_id),
        _build_project(survey_id),
        _build_scoring(survey_id),
        _build_consent_sq(survey_id, survey.consent_text),
    ]
    for i, q in enumerate(survey.demographics, start=1):
        elements.append(_build_demo_sq(survey_id, q, i))
    for i, s in enumerate(survey.scales, start=1):
        elements.append(_build_scale_sq(survey_id, s, i))
    if survey.attention_check is not None:
        elements.append(_build_attention_sq(survey_id, survey.attention_check))
    elements.append(_build_end_sq(survey_id, survey.completion_code))
    return {
        "SurveyEntry": _build_survey_entry(survey_id, rs_id, survey.title),
        "SurveyElements": elements,
    }


def _build_survey_entry(survey_id: str, rs_id: str, title: str) -> dict:
    return {
        "SurveyID": survey_id,
        "SurveyName": title,
        "SurveyDescription": None,
        "SurveyOwnerID": "UR_GENERATED",
        "SurveyBrandID": "generated",
        "DivisionID": None,
        "SurveyLanguage": "KO",
        "SurveyActiveResponseSet": rs_id,
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


def _build_response_set(survey_id: str, rs_id: str) -> dict:
    return {
        "SurveyID": survey_id,
        "Element": "RS",
        "PrimaryAttribute": rs_id,
        "SecondaryAttribute": "Default Response Set",
        "TertiaryAttribute": None,
        "Payload": None,
    }


def _build_question_count(survey_id: str) -> dict:
    return {
        "SurveyID": survey_id,
        "Element": "QC",
        "PrimaryAttribute": "Survey Question Count",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": None,
    }


def _build_survey_statistics(survey_id: str) -> dict:
    return {
        "SurveyID": survey_id,
        "Element": "STAT",
        "PrimaryAttribute": "Survey Statistics",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": {"MobileCompatible": True, "ID": "Survey Statistics"},
    }


def _build_project(survey_id: str) -> dict:
    return {
        "SurveyID": survey_id,
        "Element": "PROJ",
        "PrimaryAttribute": "CORE",
        "SecondaryAttribute": "1.1.0",
        "TertiaryAttribute": None,
        "Payload": {"ProjectCategory": "CORE", "SchemaVersion": "1.1.0"},
    }


def _build_scoring(survey_id: str) -> dict:
    return {
        "SurveyID": survey_id,
        "Element": "SCO",
        "PrimaryAttribute": "Scoring",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": {
            "ScoringCategories": [],
            "ScoringCategoryGroups": [],
            "ScoringSummaryCategory": None,
            "ScoringSummaryAfterQuestions": 0,
            "ScoringSummaryAfterSurvey": 0,
            "DefaultScoringCategory": None,
            "AutoScoringCategory": None,
        },
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
            "ValidationMessage": None,
            "PreviousButton": "",
            "NextButton": "",
            "SkinLibrary": "qualtrics",
            "SkinType": "MQ",
            "Skin": "qbase-fluid",
            "NewScoring": 1,
        },
    }


def _common_q_fields(qid: str, n_choices: int = 0, n_answers: int = 0) -> dict:
    """Bookkeeping fields Qualtrics writes on every question payload."""
    return {
        "DefaultChoices": False,
        "DataVisibility": {"Private": False, "Hidden": False},
        "GradingData": [],
        "NextChoiceId": n_choices + 1,
        "NextAnswerId": n_answers + 1,
        "QuestionID": qid,
    }


_FORCE_RESPONSE_ON = {
    "Settings": {"ForceResponse": "ON", "ForceResponseType": "ON", "Type": "None"},
}
_FORCE_RESPONSE_OFF = {
    "Settings": {"ForceResponse": "OFF", "Type": "None"},
}


def _build_consent_sq(survey_id: str, consent_text: str) -> dict:
    qid = "QID_CONSENT"
    payload: dict = {
        "QuestionText": consent_text,
        "DataExportTag": "Q_CONSENT",
        "QuestionType": "DB",
        "Selector": "TB",
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": "Consent",
        "Validation": _FORCE_RESPONSE_OFF,
        "Language": [],
    }
    payload.update(_common_q_fields(qid))
    return {
        "SurveyID": survey_id,
        "Element": "SQ",
        "PrimaryAttribute": qid,
        "SecondaryAttribute": "Consent text",
        "TertiaryAttribute": None,
        "Payload": payload,
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
        "Validation": _FORCE_RESPONSE_ON,
        "Language": [],
    }
    if sub is not None:
        payload["SubSelector"] = sub
    if q.choices:
        payload["Choices"] = {
            str(i + 1): {"Display": c} for i, c in enumerate(q.choices)
        }
        payload["ChoiceOrder"] = list(range(1, len(q.choices) + 1))
    payload.update(_common_q_fields(qid, n_choices=len(q.choices)))
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
    # Qualtrics Matrix RecodeValues operates on Answer columns (the 1-7 Likert
    # points) globally for all rows, so it cannot express per-row reversal.
    # We carry [REVERSE] markers through to QuestionDescription only; researchers
    # apply the 8-x flip in their analysis pipeline (R/SPSS/pandas).
    qid = f"QID_SCALE_{idx}"
    n = len(scale.statements)
    invalid = [i for i in scale.reverse_indices if i < 1 or i > n]
    if invalid:
        raise ValueError(
            f"SCALE '{scale.name}' REVERSE index 범위 초과: {invalid} "
            f"(statements {n}개)"
        )
    desc = f"{scale.name} Scale"
    if scale.reverse_indices:
        rev = ",".join(str(i) for i in scale.reverse_indices)
        desc = f"{desc} [REVERSE: {rev}]"
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
            "WhiteSpace": "OFF",
            "MobileFirst": True,
        },
        "QuestionDescription": desc,
        "Choices": {
            str(i + 1): {"Display": s} for i, s in enumerate(scale.statements)
        },
        "ChoiceOrder": list(range(1, n + 1)),
        "Answers": {
            str(i + 1): {"Display": LIKERT_7POINT[i]} for i in range(7)
        },
        "AnswerOrder": list(range(1, 8)),
        "ChoiceDataExportTags": False,
        "Validation": _FORCE_RESPONSE_ON,
        "Language": [],
    }
    payload.update(_common_q_fields(qid, n_choices=n, n_answers=7))
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
    qid = "QID_ATTENTION"
    payload: dict = {
        "QuestionText": attn.text,
        "DataExportTag": "Q_ATTENTION",
        "QuestionType": "MC",
        "Selector": "SAVR",
        "SubSelector": "TX",
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": "Attention check",
        "Choices": dict(_ATTENTION_CHOICES),
        "ChoiceOrder": list(range(1, 8)),
        "Validation": _FORCE_RESPONSE_ON,
        "Language": [],
        "AttentionExpected": attn.expected,
    }
    payload.update(_common_q_fields(qid, n_choices=7))
    return {
        "SurveyID": survey_id,
        "Element": "SQ",
        "PrimaryAttribute": qid,
        "SecondaryAttribute": "Attention check",
        "TertiaryAttribute": None,
        "Payload": payload,
    }


def _build_end_sq(survey_id: str, code: str) -> dict:
    qid = "QID_END"
    text = (
        f"설문에 참여해 주셔서 감사합니다.\n\n"
        f"Prolific Completion Code: {code}\n\n"
        f"위 코드를 Prolific에 입력하셔야 보상이 지급됩니다."
    )
    payload: dict = {
        "QuestionText": text,
        "DataExportTag": "Q_END",
        "QuestionType": "DB",
        "Selector": "TB",
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": "End",
        "Validation": _FORCE_RESPONSE_OFF,
        "Language": [],
    }
    payload.update(_common_q_fields(qid))
    return {
        "SurveyID": survey_id,
        "Element": "SQ",
        "PrimaryAttribute": qid,
        "SecondaryAttribute": "End message",
        "TertiaryAttribute": None,
        "Payload": payload,
    }


def _block(block_id: str, description: str, qids: list[str]) -> dict:
    return {
        "Type": "Standard",
        "SubType": "",
        "Description": description,
        "ID": block_id,
        "BlockElements": [
            {"Type": "Question", "QuestionID": qid} for qid in qids
        ],
    }


def _build_blocks(survey_id: str, survey: SurveyInput) -> dict:
    blocks: list[dict] = [
        _block("BL_CONSENT", "Consent", ["QID_CONSENT"]),
        _block(
            "BL_DEMOGRAPHICS",
            "Demographics",
            [f"QID_DEMO_{i}" for i in range(1, len(survey.demographics) + 1)],
        ),
    ]
    for i, s in enumerate(survey.scales, start=1):
        blocks.append(_block(f"BL_SCALE_{i}", f"{s.name} Scale", [f"QID_SCALE_{i}"]))
    if survey.attention_check is not None:
        blocks.append(_block("BL_ATTENTION", "Attention Check", ["QID_ATTENTION"]))
    blocks.append(_block("BL_END", "End", ["QID_END"]))
    # Qualtrics expects the BL Payload as a dict keyed by stringified indices,
    # not a list. List-shaped payloads are silently dropped on import.
    payload = {str(i): block for i, block in enumerate(blocks)}
    return {
        "SurveyID": survey_id,
        "Element": "BL",
        "PrimaryAttribute": "Survey Blocks",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": payload,
    }


def _build_flow(survey_id: str, survey: SurveyInput) -> dict:
    block_ids: list[str] = ["BL_CONSENT", "BL_DEMOGRAPHICS"]
    for i in range(1, len(survey.scales) + 1):
        block_ids.append(f"BL_SCALE_{i}")
    if survey.attention_check is not None:
        block_ids.append("BL_ATTENTION")
    block_ids.append("BL_END")

    flow_nodes: list[dict] = [
        {
            "Type": "EmbeddedData",
            "FlowID": "FL_2",
            "EmbeddedData": [
                {
                    "Description": "PROLIFIC_PID",
                    "Type": "Recipient",
                    "Field": "PROLIFIC_PID",
                    "VariableType": "String",
                    "DataVisibility": [],
                    "AnalyzeText": False,
                    "Value": "",
                },
            ],
        },
    ]
    next_id = 3
    for bid in block_ids:
        flow_nodes.append({
            "Type": "Standard",
            "ID": bid,
            "FlowID": f"FL_{next_id}",
        })
        next_id += 1

    return {
        "SurveyID": survey_id,
        "Element": "FL",
        "PrimaryAttribute": "Survey Flow",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": {
            "Type": "Root",
            "FlowID": "FL_1",
            "Properties": {"Count": next_id - 1},
            "Flow": flow_nodes,
        },
    }
