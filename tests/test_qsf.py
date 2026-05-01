"""parse_text 파서 단위 테스트."""

import pytest

from lib.qsf import parse_text


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
    for i in range(8):
        text += f"## SCALE: S{i}\nANCHOR: 7-point Likert\n- a.\n"
    text += "## END\nCOMPLETION_CODE: ABC12345\n"
    with pytest.raises(ValueError, match="최대 7"):
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


def test_seven_scales_allowed():
    text = "# SURVEY: x\n## CONSENT\n" + ("a" * 100) + "\n"
    for i in range(1, 8):
        text += f"## SCALE: S{i}\nANCHOR: Likert\n- item\n"
    text += "## END\nCOMPLETION_CODE: ABC123\n"
    survey = parse_text(text)
    assert len(survey.scales) == 7


def test_eight_scales_rejected():
    text = "# SURVEY: x\n## CONSENT\n" + ("a" * 100) + "\n"
    for i in range(1, 9):
        text += f"## SCALE: S{i}\nANCHOR: Likert\n- item\n"
    text += "## END\nCOMPLETION_CODE: ABC123\n"
    with pytest.raises(ValueError, match="최대 7"):
        parse_text(text)
