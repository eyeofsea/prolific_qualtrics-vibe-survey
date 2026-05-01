"""parse_text / inject_into_template fixture 5종."""

import pytest

from lib.qsf import parse_text, inject_into_template, export
from lib.validate import QSFValidator


# ── Fixture inputs ─────────────────────────────────────

CONSENT_TEXT = (
    "본 연구는 직장인의 변화 적응성을 조사합니다. 응답은 익명 처리되며 "
    "학술 목적으로만 사용됩니다. 참여는 자발적이며 언제든 중단할 수 있습니다."
)

MINIMAL = f"""# SURVEY: 최소 설문

## CONSENT
{CONSENT_TEXT}

## DEMOGRAPHICS
Q: 연령대는?
TYPE: SingleChoice
- 19-29세
- 30-39세

## SCALE: AS
ANCHOR: 7-point Likert
- 나는 변화에 적응한다.
- 변화는 어렵다. [REVERSE]

## END
COMPLETION_CODE: ABC12345
"""

WITH_ATTENTION = f"""# SURVEY: 주의검사 포함

## CONSENT
{CONSENT_TEXT}

## DEMOGRAPHICS
Q: 직무 분야는?
TYPE: SingleChoice
- IT
- 마케팅

## SCALE: AS
ANCHOR: 7-point Likert
- 변화에 적응한다.

## ATTENTION_CHECK
TEXT: '5'를 선택하세요.
EXPECTED: 5

## END
COMPLETION_CODE: XYZ98765
"""

ALL_FIVE_SCALES = f"""# SURVEY: 5개 척도

## CONSENT
{CONSENT_TEXT}

## DEMOGRAPHICS
Q: 연령은?
TYPE: SingleChoice
- 20대
- 30대

## SCALE: AS
ANCHOR: 7-point Likert
- 항목1.
- 항목2.

## SCALE: RC
ANCHOR: 7-point Likert
- 항목1.
- 항목2. [REVERSE]

## SCALE: ID
ANCHOR: 7-point Likert
- 항목1.

## SCALE: DV
ANCHOR: 7-point Likert
- 항목1.
- 항목2.

## SCALE: HCD
ANCHOR: 7-point Likert
- 항목1.
- 항목2.
- 항목3.

## END
COMPLETION_CODE: FIVE5555
"""

CUSTOM_SCALE_NAME = f"""# SURVEY: 커스텀 척도명

## CONSENT
{CONSENT_TEXT}

## DEMOGRAPHICS
Q: 성별은?
TYPE: SingleChoice
- 남
- 여

## SCALE: MyCustomScale
ANCHOR: 7-point Likert
- 항목1.
- 항목2.

## END
COMPLETION_CODE: CUST1234
"""

MULTICHOICE_AND_TEXT = f"""# SURVEY: 다양한 type

## CONSENT
{CONSENT_TEXT}

## DEMOGRAPHICS
Q: 사용 도구는? (복수)
TYPE: MultiChoice
- VSCode
- IntelliJ
- Vim

Q: 한 줄 자기소개?
TYPE: Text

## SCALE: AS
ANCHOR: 7-point Likert
- 적응한다.

## END
COMPLETION_CODE: MIX12345
"""


# ── parse_text 테스트 ───────────────────────────────────

def test_parse_minimal():
    s = parse_text(MINIMAL)
    assert s.title == "최소 설문"
    assert CONSENT_TEXT in s.consent_text
    assert len(s.demographics) == 1
    assert s.demographics[0].text == "연령대는?"
    assert s.demographics[0].type == "SingleChoice"
    assert s.demographics[0].choices == ["19-29세", "30-39세"]
    assert len(s.scales) == 1
    assert s.scales[0].name == "AS"
    assert len(s.scales[0].statements) == 2
    assert s.scales[0].reverse_indices == [2]
    assert s.attention_check is None
    assert s.completion_code == "ABC12345"


def test_parse_with_attention():
    s = parse_text(WITH_ATTENTION)
    assert s.attention_check is not None
    assert s.attention_check.text == "'5'를 선택하세요."
    assert s.attention_check.expected == 5


def test_parse_all_five_scales():
    s = parse_text(ALL_FIVE_SCALES)
    assert [sc.name for sc in s.scales] == ["AS", "RC", "ID", "DV", "HCD"]
    assert s.scales[1].reverse_indices == [2]


def test_parse_custom_scale_name_maps_to_first_free_slot():
    s = parse_text(CUSTOM_SCALE_NAME)
    assert s.scales[0].name == "MyCustomScale"


def test_parse_multichoice_and_text():
    s = parse_text(MULTICHOICE_AND_TEXT)
    assert s.demographics[0].type == "MultiChoice"
    assert s.demographics[1].type == "Text"
    assert s.demographics[1].choices == []


def test_parse_too_many_scales_raises():
    text = "# SURVEY: x\n## CONSENT\n" + ("a" * 100) + "\n"
    for i in range(6):
        text += f"## SCALE: S{i}\nANCHOR: 7-point Likert\n- a.\n"
    text += "## END\nCOMPLETION_CODE: ABC12345\n"
    with pytest.raises(ValueError, match="SCALE 은 최대 5개"):
        parse_text(text)


def test_parse_missing_title_raises():
    with pytest.raises(ValueError, match="SURVEY"):
        parse_text("## CONSENT\nfoo\n")


def test_parse_missing_consent_raises():
    text = (
        "# SURVEY: x\n## DEMOGRAPHICS\nQ: a?\nTYPE: SingleChoice\n- a\n"
        "## END\nCOMPLETION_CODE: ABC12345\n"
    )
    with pytest.raises(ValueError, match="CONSENT"):
        parse_text(text)


def test_parse_demographics_unknown_type_raises():
    text = (
        "# SURVEY: x\n## CONSENT\n" + ("a" * 100) + "\n"
        "## DEMOGRAPHICS\nQ: a?\nTYPE: WeirdType\n- a\n"
        "## END\nCOMPLETION_CODE: ABC12345\n"
    )
    with pytest.raises(ValueError, match="알 수 없"):
        parse_text(text)


# ── inject_into_template 테스트 ─────────────────────────

@pytest.mark.parametrize(
    "fixture",
    [MINIMAL, WITH_ATTENTION, ALL_FIVE_SCALES, CUSTOM_SCALE_NAME, MULTICHOICE_AND_TEXT],
)
def test_inject_then_validate_passes(fixture, template):
    s = parse_text(fixture)
    qsf = inject_into_template(s, template)
    report = QSFValidator(qsf, template=template).run()
    assert not report.is_blocked, (
        f"Errors: {[(e.code, e.message) for e in report.errors]}"
    )


def test_inject_preserves_prolific_pid_embed(template):
    s = parse_text(MINIMAL)
    qsf = inject_into_template(s, template)
    flow = next(
        e for e in qsf["SurveyElements"] if e.get("Element") == "FL"
    )["Payload"]
    found = False
    stack = [flow]
    while stack:
        node = stack.pop()
        if node.get("Type") == "EmbeddedData":
            for ed in node.get("EmbeddedData", []) or []:
                if ed.get("Field") == "PROLIFIC_PID":
                    found = True
        for child in node.get("Flow", []) or []:
            stack.append(child)
    assert found


def test_inject_sets_survey_name(template):
    s = parse_text(MINIMAL)
    qsf = inject_into_template(s, template)
    assert qsf["SurveyEntry"]["SurveyName"] == "최소 설문"


def test_inject_drops_unused_scale_blocks(template):
    s = parse_text(MINIMAL)  # only AS
    qsf = inject_into_template(s, template)
    blocks = next(
        e for e in qsf["SurveyElements"] if e.get("Element") == "BL"
    )["Payload"]
    block_ids = {b["ID"] for b in blocks}
    # AS remains, others (RC/ID/DV/HCD) removed
    assert "BL_SCALE_AS" in block_ids
    assert "BL_SCALE_RC" not in block_ids
    assert "BL_SCALE_ID" not in block_ids
    assert "BL_SCALE_DV" not in block_ids
    assert "BL_SCALE_HCD" not in block_ids


def test_inject_keeps_all_five_scales(template):
    s = parse_text(ALL_FIVE_SCALES)
    qsf = inject_into_template(s, template)
    blocks = next(
        e for e in qsf["SurveyElements"] if e.get("Element") == "BL"
    )["Payload"]
    block_ids = {b["ID"] for b in blocks}
    for slot in ["AS", "RC", "ID", "DV", "HCD"]:
        assert f"BL_SCALE_{slot}" in block_ids


def test_inject_writes_completion_code(template):
    s = parse_text(MINIMAL)
    qsf = inject_into_template(s, template)
    end = next(
        e for e in qsf["SurveyElements"]
        if e.get("Element") == "SQ" and e.get("PrimaryAttribute") == "QID_END"
    )
    assert "ABC12345" in end["Payload"]["QuestionText"]
    assert "PLACEHOLDER" not in end["Payload"]["QuestionText"]


def test_inject_reverse_index_creates_recode(template):
    s = parse_text(MINIMAL)
    qsf = inject_into_template(s, template)
    as_q = next(
        e for e in qsf["SurveyElements"]
        if e.get("Element") == "SQ" and e.get("PrimaryAttribute") == "QID_SCALE_AS"
    )
    recode = as_q["Payload"].get("RecodeValues", {})
    # statement #2 reversed → 8-2 = 6
    assert recode["1"] == "1"
    assert recode["2"] == "6"


def test_inject_demographics_replaces_template_questions(template):
    s = parse_text(WITH_ATTENTION)
    qsf = inject_into_template(s, template)
    demo_block = next(
        b for b in next(
            e for e in qsf["SurveyElements"] if e.get("Element") == "BL"
        )["Payload"]
        if b["ID"] == "BL_DEMOGRAPHICS"
    )
    assert len(demo_block["BlockElements"]) == 1
    qid = demo_block["BlockElements"][0]["QuestionID"]
    q = next(
        e for e in qsf["SurveyElements"]
        if e.get("Element") == "SQ" and e.get("PrimaryAttribute") == qid
    )
    assert q["Payload"]["QuestionText"] == "직무 분야는?"


def test_export_writes_utf8(tmp_path, template):
    s = parse_text(MINIMAL)
    qsf = inject_into_template(s, template)
    path = tmp_path / "out.qsf"
    export(qsf, str(path))
    text = path.read_text(encoding="utf-8")
    assert "최소 설문" in text
    assert "ABC12345" in text


def test_inject_attention_check_text(template):
    s = parse_text(WITH_ATTENTION)
    qsf = inject_into_template(s, template)
    att = next(
        e for e in qsf["SurveyElements"]
        if e.get("Element") == "SQ" and e.get("PrimaryAttribute") == "QID_ATTENTION"
    )
    assert "'5'를 선택하세요." in att["Payload"]["QuestionText"]


def test_inject_no_attention_drops_block(template):
    s = parse_text(MINIMAL)  # no attention
    qsf = inject_into_template(s, template)
    blocks = next(
        e for e in qsf["SurveyElements"] if e.get("Element") == "BL"
    )["Payload"]
    block_ids = {b["ID"] for b in blocks}
    assert "BL_ATTENTION" not in block_ids
