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


def test_demographics_three_types():
    survey = _minimal_survey().model_copy(update={
        "demographics": [
            Question(text="연령대?", type="SingleChoice", choices=["20대", "30대", "40대"]),
            Question(text="관심 분야는?", type="MultiChoice", choices=["A", "B", "C"]),
            Question(text="자유 의견", type="Text", choices=[]),
        ],
    })
    qsf = build_qsf(survey)
    demos = [e for e in qsf["SurveyElements"]
             if e.get("Element") == "SQ"
             and e.get("PrimaryAttribute", "").startswith("QID_DEMO_")]
    assert len(demos) == 3
    by_id = {d["PrimaryAttribute"]: d for d in demos}
    assert by_id["QID_DEMO_1"]["Payload"]["QuestionType"] == "MC"
    assert by_id["QID_DEMO_1"]["Payload"]["Selector"] == "SAVR"
    assert by_id["QID_DEMO_2"]["Payload"]["Selector"] == "MAVR"
    assert by_id["QID_DEMO_3"]["Payload"]["QuestionType"] == "TE"
    assert by_id["QID_DEMO_1"]["Payload"]["Choices"]["1"]["Display"] == "20대"
    assert by_id["QID_DEMO_1"]["Payload"]["DataExportTag"] == "Q_DEMO_1"


def test_single_matrix_scale_with_arbitrary_name_and_reverse():
    survey = _minimal_survey().model_copy(update={
        "scales": [
            Scale(
                name="WBI",  # arbitrary, not from {AS,RC,ID,DV,HCD}
                anchor="7-point Likert",
                statements=["나는 빠르게 적응한다.", "변화가 두렵다.", "기회를 만든다."],
                reverse_indices=[2],
            ),
        ],
    })
    qsf = build_qsf(survey)
    scale = next(
        (e for e in qsf["SurveyElements"]
         if e.get("PrimaryAttribute") == "QID_SCALE_1"),
        None,
    )
    assert scale is not None
    p = scale["Payload"]
    assert p["QuestionType"] == "Matrix"
    assert p["Selector"] == "Likert"
    assert p["SubSelector"] == "SingleAnswer"
    assert p["DataExportTag"] == "Q_SCALE_1"  # stable index, not name
    assert p["QuestionDescription"] == "WBI Scale"  # name reflected here
    assert len(p["Choices"]) == 3
    assert p["Choices"]["1"]["Display"] == "나는 빠르게 적응한다."
    assert len(p["Answers"]) == 7
    assert p["Answers"]["1"]["Display"] == "전혀 동의하지 않는다"
    assert p["Answers"]["7"]["Display"] == "매우 동의한다"
    assert p["RecodeValues"] == {"1": "1", "2": "6", "3": "3"}


def test_seven_scales_with_mixed_names_supported():
    scales = [
        Scale(name=name, anchor="7-point Likert",
              statements=["문항 a", "문항 b"], reverse_indices=[])
        for name in ["AS", "WBI", "Resilience", "MyScale", "스케일", "Foo7", "G"]
    ]
    survey = _minimal_survey().model_copy(update={"scales": scales})
    qsf = build_qsf(survey)
    scale_qs = [e for e in qsf["SurveyElements"]
                if e.get("PrimaryAttribute", "").startswith("QID_SCALE_")]
    qids = sorted(e["PrimaryAttribute"] for e in scale_qs)
    assert qids == [f"QID_SCALE_{i}" for i in range(1, 8)]
    descs = [e["Payload"]["QuestionDescription"] for e in
             sorted(scale_qs, key=lambda e: e["PrimaryAttribute"])]
    assert descs == [f"{n} Scale" for n in
                     ["AS", "WBI", "Resilience", "MyScale", "스케일", "Foo7", "G"]]


def test_no_scales_produces_zero_scale_sqs():
    qsf = build_qsf(_minimal_survey())
    scale_qids = [e for e in qsf["SurveyElements"]
                  if e.get("PrimaryAttribute", "").startswith("QID_SCALE_")]
    assert scale_qids == []


def test_attention_check_present_when_provided():
    survey = _minimal_survey().model_copy(update={
        "attention_check": AttentionCheck(text="5번을 선택하세요.", expected=5),
    })
    qsf = build_qsf(survey)
    att = next(
        (e for e in qsf["SurveyElements"]
         if e.get("PrimaryAttribute") == "QID_ATTENTION"),
        None,
    )
    assert att is not None
    p = att["Payload"]
    assert p["QuestionType"] == "MC"
    assert p["Selector"] == "SAVR"
    assert p["QuestionText"] == "5번을 선택하세요."
    assert p["AttentionExpected"] == 5
    assert len(p["Choices"]) == 7


def test_attention_check_absent_when_none():
    qsf = build_qsf(_minimal_survey())  # attention_check=None
    att = [e for e in qsf["SurveyElements"]
           if e.get("PrimaryAttribute") == "QID_ATTENTION"]
    assert att == []


def test_end_question_contains_completion_code():
    qsf = build_qsf(_minimal_survey())  # completion_code="ABC12345"
    end = next(
        (e for e in qsf["SurveyElements"]
         if e.get("PrimaryAttribute") == "QID_END"),
        None,
    )
    assert end is not None
    text = end["Payload"]["QuestionText"]
    assert "ABC12345" in text
    assert "코드" in text
    assert end["Payload"]["QuestionType"] == "DB"


def test_blocks_for_minimal_survey():
    qsf = build_qsf(_minimal_survey())
    bl = _find_element(qsf, "BL", "Survey Blocks")
    assert bl is not None
    block_ids = [b["ID"] for b in bl["Payload"]]
    assert block_ids == ["BL_CONSENT", "BL_DEMOGRAPHICS", "BL_END"]


def test_blocks_with_scales_and_attention():
    survey = _minimal_survey().model_copy(update={
        "demographics": [Question(text="Q?", type="Text", choices=[])],
        "scales": [
            Scale(name="WBI", anchor="7-point Likert",
                  statements=["a"], reverse_indices=[]),
            Scale(name="Resilience", anchor="7-point Likert",
                  statements=["b"], reverse_indices=[]),
        ],
        "attention_check": AttentionCheck(text="t", expected=5),
    })
    qsf = build_qsf(survey)
    bl = _find_element(qsf, "BL", "Survey Blocks")
    block_ids = [b["ID"] for b in bl["Payload"]]
    assert block_ids == [
        "BL_CONSENT",
        "BL_DEMOGRAPHICS",
        "BL_SCALE_1",
        "BL_SCALE_2",
        "BL_ATTENTION",
        "BL_END",
    ]
    demo_block = next(b for b in bl["Payload"] if b["ID"] == "BL_DEMOGRAPHICS")
    assert demo_block["BlockElements"] == [{"Type": "Question", "QuestionID": "QID_DEMO_1"}]
    scale1_block = next(b for b in bl["Payload"] if b["ID"] == "BL_SCALE_1")
    assert scale1_block["Description"] == "WBI Scale"
    assert scale1_block["BlockElements"] == [{"Type": "Question", "QuestionID": "QID_SCALE_1"}]


def test_survey_flow_has_prolific_pid_and_blocks_in_order():
    survey = _minimal_survey().model_copy(update={
        "scales": [
            Scale(name="X", anchor="7-point Likert",
                  statements=["a"], reverse_indices=[]),
        ],
        "attention_check": AttentionCheck(text="t", expected=5),
    })
    qsf = build_qsf(survey)
    fl = _find_element(qsf, "FL", "Survey Flow")
    assert fl is not None
    flow = fl["Payload"]["Flow"]
    assert flow[0]["Type"] == "EmbeddedData"
    fields = [ed["Field"] for ed in flow[0]["EmbeddedData"]]
    assert "PROLIFIC_PID" in fields
    standard_ids = [n["ID"] for n in flow if n.get("Type") == "Standard"]
    assert standard_ids == [
        "BL_CONSENT", "BL_DEMOGRAPHICS", "BL_SCALE_1", "BL_ATTENTION", "BL_END",
    ]
    flow_ids = [n["FlowID"] for n in flow]
    import re as _re
    for fid in flow_ids:
        assert _re.match(r"^FL_\d+$", fid), f"bad FlowID: {fid}"
    assert len(set(flow_ids)) == len(flow_ids)  # unique
