"""22개 validation rule × pass/fail 케이스."""

import copy
import json
from pathlib import Path

import pytest

from lib.qsf import parse_text, inject_into_template
from lib.validate import QSFValidator


REPO_ROOT = Path(__file__).parent.parent


# ── 기준 QSF (검증 통과해야 함) ─────────────────────────

@pytest.fixture
def baseline_qsf(template):
    text = """# SURVEY: 테스트 설문

## CONSENT
""" + ("이 설문은 학술 목적으로만 사용됩니다. " * 5) + """

## DEMOGRAPHICS
Q: 연령은?
TYPE: SingleChoice
- 20대
- 30대

## SCALE: AS
ANCHOR: 7-point Likert
- 항목1.
- 항목2.

## END
COMPLETION_CODE: GOOD1234
"""
    s = parse_text(text)
    return inject_into_template(s, template)


def _codes(report):
    return [i.code for i in report.issues]


def test_baseline_passes(baseline_qsf, template):
    r = QSFValidator(baseline_qsf, template=template).run()
    assert not r.is_blocked, [(e.code, e.message) for e in r.errors]


# ── 1. MISSING_TOPLEVEL_KEY ─────────────────────────────

def test_missing_toplevel_key_fail():
    qsf = {"SurveyEntry": {"SurveyID": "x", "SurveyName": "y", "SurveyLanguage": "KO"}}
    r = QSFValidator(qsf).run()
    assert "MISSING_TOPLEVEL_KEY" in _codes(r)


def test_missing_toplevel_key_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "MISSING_TOPLEVEL_KEY" not in _codes(r)


# ── 2. MISSING_SURVEY_ENTRY_FIELD ───────────────────────

def test_missing_survey_entry_field_fail(baseline_qsf):
    baseline_qsf["SurveyEntry"]["SurveyName"] = ""
    r = QSFValidator(baseline_qsf).run()
    assert "MISSING_SURVEY_ENTRY_FIELD" in _codes(r)


def test_missing_survey_entry_field_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "MISSING_SURVEY_ENTRY_FIELD" not in _codes(r)


# ── 3. MISSING_PROLIFIC_PID_EMBED ───────────────────────

def test_missing_prolific_pid_embed_fail(baseline_qsf):
    flow = next(e for e in baseline_qsf["SurveyElements"] if e["Element"] == "FL")
    flow["Payload"]["Flow"] = [
        f for f in flow["Payload"]["Flow"] if f.get("Type") != "EmbeddedData"
    ]
    r = QSFValidator(baseline_qsf).run()
    assert "MISSING_PROLIFIC_PID_EMBED" in _codes(r)


def test_missing_prolific_pid_embed_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "MISSING_PROLIFIC_PID_EMBED" not in _codes(r)


# ── 4. ORPHAN_BLOCK_REF ─────────────────────────────────

def test_orphan_block_ref_fail(baseline_qsf):
    flow = next(e for e in baseline_qsf["SurveyElements"] if e["Element"] == "FL")
    flow["Payload"]["Flow"].append(
        {"Type": "Standard", "ID": "BL_GHOST", "FlowID": "FL_99"}
    )
    r = QSFValidator(baseline_qsf).run()
    assert "ORPHAN_BLOCK_REF" in _codes(r)


def test_orphan_block_ref_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "ORPHAN_BLOCK_REF" not in _codes(r)


# ── 5. ORPHAN_QUESTION_REF ──────────────────────────────

def test_orphan_question_ref_fail(baseline_qsf):
    blocks = next(e for e in baseline_qsf["SurveyElements"] if e["Element"] == "BL")
    blocks["Payload"][0]["BlockElements"].append(
        {"Type": "Question", "QuestionID": "QID_GHOST"}
    )
    r = QSFValidator(baseline_qsf).run()
    assert "ORPHAN_QUESTION_REF" in _codes(r)


def test_orphan_question_ref_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "ORPHAN_QUESTION_REF" not in _codes(r)


# ── 6. INVALID_FLOW_ID ──────────────────────────────────

def test_invalid_flow_id_fail(baseline_qsf):
    flow = next(e for e in baseline_qsf["SurveyElements"] if e["Element"] == "FL")
    flow["Payload"]["Flow"][0]["FlowID"] = "FLOW-BAD"
    r = QSFValidator(baseline_qsf).run()
    assert "INVALID_FLOW_ID" in _codes(r)


def test_invalid_flow_id_duplicate_fail(baseline_qsf):
    flow = next(e for e in baseline_qsf["SurveyElements"] if e["Element"] == "FL")
    flow["Payload"]["Flow"][0]["FlowID"] = "FL_5"
    flow["Payload"]["Flow"][1]["FlowID"] = "FL_5"
    r = QSFValidator(baseline_qsf).run()
    assert "INVALID_FLOW_ID" in _codes(r)


def test_invalid_flow_id_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "INVALID_FLOW_ID" not in _codes(r)


# ── 7. MATRIX_MISSING_ANSWERS ───────────────────────────

def test_matrix_missing_answers_fail(baseline_qsf):
    as_q = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_SCALE_AS"
    )
    del as_q["Payload"]["Answers"]
    r = QSFValidator(baseline_qsf).run()
    assert "MATRIX_MISSING_ANSWERS" in _codes(r)


def test_matrix_missing_answers_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "MATRIX_MISSING_ANSWERS" not in _codes(r)


# ── 8. MATRIX_ANCHOR_COUNT ──────────────────────────────

def test_matrix_anchor_count_warn(baseline_qsf):
    as_q = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_SCALE_AS"
    )
    as_q["Payload"]["Answers"] = {str(i): {"Display": str(i)} for i in range(1, 6)}
    r = QSFValidator(baseline_qsf).run()
    assert "MATRIX_ANCHOR_COUNT" in _codes(r)


def test_matrix_anchor_count_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "MATRIX_ANCHOR_COUNT" not in _codes(r)


# ── 9. EMPTY_QUESTION_TEXT ──────────────────────────────

def test_empty_question_text_fail(baseline_qsf):
    consent = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_CONSENT_1"
    )
    consent["Payload"]["QuestionText"] = ""
    r = QSFValidator(baseline_qsf).run()
    assert "EMPTY_QUESTION_TEXT" in _codes(r)


def test_empty_question_text_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "EMPTY_QUESTION_TEXT" not in _codes(r)


# ── 10. INVALID_QUESTION_TYPE ───────────────────────────

def test_invalid_question_type_fail(baseline_qsf):
    consent = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_CONSENT_1"
    )
    consent["Payload"]["QuestionType"] = "WeirdType"
    r = QSFValidator(baseline_qsf).run()
    assert "INVALID_QUESTION_TYPE" in _codes(r)


def test_invalid_question_type_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "INVALID_QUESTION_TYPE" not in _codes(r)


# ── 11. ENCODING_ARTIFACT ───────────────────────────────

def test_encoding_artifact_fail(baseline_qsf):
    consent = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_CONSENT_1"
    )
    consent["Payload"]["QuestionText"] = "﻿" + consent["Payload"]["QuestionText"]
    r = QSFValidator(baseline_qsf).run()
    assert "ENCODING_ARTIFACT" in _codes(r)


def test_encoding_artifact_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "ENCODING_ARTIFACT" not in _codes(r)


# ── 12. BRANCH_REFS_MISSING ─────────────────────────────

def test_branch_refs_missing_fail(baseline_qsf):
    flow = next(e for e in baseline_qsf["SurveyElements"] if e["Element"] == "FL")
    flow["Payload"]["Flow"].append({
        "Type": "Branch",
        "FlowID": "FL_77",
        "BranchLogic": {},
        "Flow": [
            {"Type": "Standard", "ID": "BL_NONEXIST", "FlowID": "FL_78"}
        ],
    })
    r = QSFValidator(baseline_qsf).run()
    assert "BRANCH_REFS_MISSING" in _codes(r)


def test_branch_refs_missing_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "BRANCH_REFS_MISSING" not in _codes(r)


# ── 13. DUPLICATE_QID ───────────────────────────────────

def test_duplicate_qid_fail(baseline_qsf):
    consent = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_CONSENT_1"
    )
    baseline_qsf["SurveyElements"].append(copy.deepcopy(consent))
    r = QSFValidator(baseline_qsf).run()
    assert "DUPLICATE_QID" in _codes(r)


def test_duplicate_qid_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "DUPLICATE_QID" not in _codes(r)


# ── 14. EMPTY_BLOCK ─────────────────────────────────────

def test_empty_block_warn(baseline_qsf):
    blocks = next(e for e in baseline_qsf["SurveyElements"] if e["Element"] == "BL")
    blocks["Payload"][0]["BlockElements"] = []
    r = QSFValidator(baseline_qsf).run()
    assert "EMPTY_BLOCK" in _codes(r)


def test_empty_block_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "EMPTY_BLOCK" not in _codes(r)


# ── 15. UNUSED_BLOCK ────────────────────────────────────

def test_unused_block_info(baseline_qsf):
    blocks = next(e for e in baseline_qsf["SurveyElements"] if e["Element"] == "BL")
    blocks["Payload"].append({
        "Type": "Standard",
        "ID": "BL_ORPHAN",
        "Description": "Orphan",
        "BlockElements": [],
    })
    r = QSFValidator(baseline_qsf).run()
    assert "UNUSED_BLOCK" in _codes(r)


def test_unused_block_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "UNUSED_BLOCK" not in _codes(r)


# ── 16. COMPLETION_CODE_MISSING ─────────────────────────

def test_completion_code_missing_warn(baseline_qsf):
    end = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_END"
    )
    end["Payload"]["QuestionText"] = "감사합니다."
    r = QSFValidator(baseline_qsf).run()
    assert "COMPLETION_CODE_MISSING" in _codes(r)


def test_completion_code_missing_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "COMPLETION_CODE_MISSING" not in _codes(r)


# ── 17. CONSENT_TOO_SHORT ───────────────────────────────

def test_consent_too_short_info(baseline_qsf):
    consent = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_CONSENT_1"
    )
    consent["Payload"]["QuestionText"] = "짧음."
    r = QSFValidator(baseline_qsf).run()
    assert "CONSENT_TOO_SHORT" in _codes(r)


def test_consent_too_short_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "CONSENT_TOO_SHORT" not in _codes(r)


# ── 18. CONSENT_TOO_LONG ────────────────────────────────

def test_consent_too_long_warn(baseline_qsf):
    consent = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_CONSENT_1"
    )
    consent["Payload"]["QuestionText"] = "가" * 1600
    r = QSFValidator(baseline_qsf).run()
    assert "CONSENT_TOO_LONG" in _codes(r)


def test_consent_too_long_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "CONSENT_TOO_LONG" not in _codes(r)


# ── 19. REVERSE_INDEX_OUT_OF_RANGE ──────────────────────

def test_reverse_index_out_of_range_fail(baseline_qsf):
    as_q = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_SCALE_AS"
    )
    as_q["Payload"]["RecodeValues"] = {"99": "1"}
    r = QSFValidator(baseline_qsf).run()
    assert "REVERSE_INDEX_OUT_OF_RANGE" in _codes(r)


def test_reverse_index_out_of_range_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "REVERSE_INDEX_OUT_OF_RANGE" not in _codes(r)


# ── 20. TEMPLATE_DRIFT ──────────────────────────────────

def test_template_drift_warn(baseline_qsf, template):
    flow = next(e for e in baseline_qsf["SurveyElements"] if e["Element"] == "FL")
    flow["Payload"]["Flow"] = [
        f for f in flow["Payload"]["Flow"] if f.get("Type") != "EmbeddedData"
    ]
    r = QSFValidator(baseline_qsf, template=template).run()
    assert "TEMPLATE_DRIFT" in _codes(r)


def test_template_drift_pass(baseline_qsf, template):
    r = QSFValidator(baseline_qsf, template=template).run()
    assert "TEMPLATE_DRIFT" not in _codes(r)


# ── 21. SMART_QUOTE_DETECTED ────────────────────────────

def test_smart_quote_detected_info(baseline_qsf):
    consent = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_CONSENT_1"
    )
    consent["Payload"]["QuestionText"] += " “smart” quote"
    r = QSFValidator(baseline_qsf).run()
    assert "SMART_QUOTE_DETECTED" in _codes(r)


def test_smart_quote_detected_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "SMART_QUOTE_DETECTED" not in _codes(r)


# ── 22. TRAILING_COMMA ──────────────────────────────────

def test_trailing_comma_warn(baseline_qsf):
    baseline_qsf["SurveyEntry"][""] = "ghost"
    r = QSFValidator(baseline_qsf).run()
    assert "TRAILING_COMMA" in _codes(r)


def test_trailing_comma_pass(baseline_qsf):
    r = QSFValidator(baseline_qsf).run()
    assert "TRAILING_COMMA" not in _codes(r)


# ── 보고서 헬퍼 ─────────────────────────────────────────

def test_report_is_blocked_only_on_errors(baseline_qsf):
    consent = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_CONSENT_1"
    )
    consent["Payload"]["QuestionText"] = "짧음."  # info
    r = QSFValidator(baseline_qsf).run()
    assert not r.is_blocked


def test_report_is_blocked_on_error(baseline_qsf):
    consent = next(
        e for e in baseline_qsf["SurveyElements"]
        if e.get("PrimaryAttribute") == "QID_CONSENT_1"
    )
    consent["Payload"]["QuestionText"] = ""
    r = QSFValidator(baseline_qsf).run()
    assert r.is_blocked
