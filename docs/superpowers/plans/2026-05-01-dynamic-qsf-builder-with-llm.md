# Dynamic QSF Builder + LLM Freeform Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rigid 5-slot template-injection approach with a dynamic QSF builder that supports 1–7 user-defined matrix scales with arbitrary scale names (e.g., `AS`, `WBI`, `Resilience`, any short label), then add an LLM-powered freeform-text → markdown normalizer (multi-provider, OS-keyring storage, human-in-the-loop). Scale names chosen by the LLM (or the user) flow through to the QSF as `QuestionDescription = "<name> Scale"`; DataExportTags use stable indices (`Q_SCALE_1` … `Q_SCALE_7`) to keep CSV column headers ASCII-safe.

**Architecture:**
- **Phase 1 (deterministic):** New `lib/qsf_builder.py` constructs the entire QSF dict from scratch (no template file). `parse_text` keeps the markdown contract; the only language change is removing the fixed `AS/RC/ID/DV/HCD` slot mapping and bumping max scales 5 → 7. Block IDs and QIDs use `BL_SCALE_<N>` / `QID_SCALE_<N>` (1-indexed); scale names appear in QuestionDescription only.
- **Phase 2 (LLM):** New `lib/llm.py` provider abstraction (Anthropic + OpenAI, auto-detected by API-key prefix). New `lib/secrets.py` wraps OS keyring. New `pages/0_⚙️_설정.py` for key management. The QSF page gains a "자유형 텍스트 정규화" expander that calls the LLM and pre-fills the markdown textarea — output is always editable (human-in-the-loop). LLM is never used to generate the QSF directly. The system prompt tells the LLM to pick scale names freely (any short label fitting the survey topic) up to 7 scales.

**Tech Stack:** Python 3.14, Streamlit 1.57, pydantic 2, pytest, anthropic SDK, openai SDK, keyring (Windows Credential Manager backend).

**Conventions locked in:**
- Each scale gets `BlockID = BL_SCALE_<N>`, `QID = QID_SCALE_<N>`, `DataExportTag = Q_SCALE_<N>` (1-indexed). User's `name` field appears only in `QuestionDescription` (free-form, accepts Korean and arbitrary labels).
- LLM defaults: Anthropic = `claude-haiku-4-5`, OpenAI = `gpt-4.1-mini`.
- Provider auto-detect: key prefix `sk-ant-` → Anthropic, else `sk-` → OpenAI; manual override available in settings page.
- Working branch: `feat/dynamic-qsf-builder`, branched off `claude/build-survey-studio-app-zjbVm`.
- No template file dependency at runtime. `templates/standard.qsf` stays in the repo for reference only.
- Tests: pytest, run from repo root.

---

## File Structure

**New files:**
- `lib/qsf_builder.py` — pure function `build_qsf(SurveyInput) → dict`. Builds SurveyEntry, SurveyOptions, SurveyFlow, SurveyBlocks, all SQ elements.
- `lib/secrets.py` — keyring wrapper for LLM API key (`get/set/delete`).
- `lib/llm.py` — LLM provider abstraction (`detect_provider`, `freeform_to_markdown`, `LLMError`).
- `pages/0_⚙️_설정.py` — settings page (API key + provider override).
- `tests/test_qsf_builder.py` — unit + integration tests for builder.
- `tests/test_secrets.py` — keyring wrapper tests (with mock).
- `tests/test_llm.py` — LLM tests with mocked SDKs.

**Modified files:**
- `lib/qsf.py` — remove `SCALE_SLOTS`, `_assign_scales_to_slots`, `_drop_unused_scale_blocks`, all `_inject_*`, `inject_into_template`, `LIKERT_7POINT`, `_find_*`, `_question_type_to_qualtrics`, `_build_demo_question_payload`, `import copy`. Bump max scales 5→7. Keep `parse_text`, dataclasses (`Question`, `Scale`, `AttentionCheck`, `SurveyInput`), `export`. The migrated logic for question type mapping and Likert anchors lives in `qsf_builder.py`.
- `pages/1_📝_QSF_변환.py` — replace template-load + `inject_into_template` with `build_qsf`. Add freeform-normalize expander above main textarea (Phase 2).
- `shared/state.py` — add `LLM_API_KEY` and `LLM_PROVIDER_OVERRIDE` keys.
- `tests/test_qsf.py` — drop slot-specific assertions, add 7-scale test, drop `inject_into_template` integration tests (moved to `test_qsf_builder.py`).
- `tests/test_validate.py` — adapt any tests that assumed template injection.
- `docs/input_format_spec.md` — remove "AS/RC/ID/DV/HCD slot mapping" wording; change max-5 → max-7; describe arbitrary scale names; add LLM-normalization note.
- `requirements.txt` — add `anthropic>=0.40.0`, `openai>=1.50.0`. (Keep existing deps.)

**Files left alone:**
- `templates/standard.qsf` — kept as schema reference; never loaded at runtime after Phase 1.
- `lib/prolific.py`, `lib/screening.py`, `lib/monitor.py`, `pages/2_🚀_Prolific_제어.py` — out of scope.

---

## Phase 1 — Dynamic QSF Builder (no LLM)

After Phase 1 ships: app fully functional, 1–7 user-defined scales with arbitrary names, no template file at runtime, all 22 validation rules pass, no LLM dependency.

### Task 1: Branch + dependency bump

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Create working branch**

```bash
cd C:/Users/Joseph/projects/prolific_qualtrics-vibe-survey
git checkout -b feat/dynamic-qsf-builder
```

- [ ] **Step 2: Add LLM SDKs to requirements**

Edit `requirements.txt` so it reads:

```
streamlit>=1.30
pydantic>=2.0
httpx>=0.25
keyring>=24.0
streamlit-autorefresh>=1.0.1
pytest>=7.4
anthropic>=0.40.0
openai>=1.50.0
```

- [ ] **Step 3: Install**

```bash
pip install -r requirements.txt
```
Expected: SDKs installed without conflict.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add anthropic and openai SDKs for LLM normalization"
```

---

### Task 2: Builder skeleton + SurveyEntry

**Files:**
- Create: `lib/qsf_builder.py`
- Create: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_qsf_builder.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: `ImportError: cannot import name 'build_qsf' from 'lib.qsf_builder'`.

- [ ] **Step 3: Write minimal implementation**

Create `lib/qsf_builder.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/qsf_builder.py tests/test_qsf_builder.py
git commit -m "feat(qsf): add qsf_builder skeleton with SurveyEntry"
```

---

### Task 3: SurveyOptions element

**Files:**
- Modify: `lib/qsf_builder.py`
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_qsf_builder.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_qsf_builder.py::test_survey_options_present -v
```
Expected: `AssertionError: assert None is not None`.

- [ ] **Step 3: Implement and append SO**

Append to `lib/qsf_builder.py`:

```python
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
```

Update `build_qsf` to append SO:

```python
def build_qsf(survey: SurveyInput) -> dict:
    survey_id = _new_survey_id()
    elements: list[dict] = [_build_survey_options(survey_id)]
    return {
        "SurveyEntry": _build_survey_entry(survey_id, survey.title),
        "SurveyElements": elements,
    }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/qsf_builder.py tests/test_qsf_builder.py
git commit -m "feat(qsf): add SurveyOptions element to builder"
```

---

### Task 4: Consent question (DB type)

**Files:**
- Modify: `lib/qsf_builder.py`
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_qsf_builder.py::test_consent_question_present -v
```
Expected: `assert None is not None`.

- [ ] **Step 3: Implement consent SQ**

Append to `lib/qsf_builder.py`:

```python
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
```

In `build_qsf`, after SO:
```python
elements.append(_build_consent_sq(survey_id, survey.consent_text))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/qsf_builder.py tests/test_qsf_builder.py
git commit -m "feat(qsf): add consent SQ to builder"
```

---

### Task 5: Demographics SQs (SingleChoice / MultiChoice / Text)

**Files:**
- Modify: `lib/qsf_builder.py`
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_qsf_builder.py::test_demographics_three_types -v
```
Expected: `assert 0 == 3`.

- [ ] **Step 3: Implement demographics builder**

Append to `lib/qsf_builder.py`:

```python
from lib.qsf import Question


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
```

In `build_qsf`, after consent:
```python
for i, q in enumerate(survey.demographics, start=1):
    elements.append(_build_demo_sq(survey_id, q, i))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/qsf_builder.py tests/test_qsf_builder.py
git commit -m "feat(qsf): add demographics SQs to builder"
```

---

### Task 6: Matrix scale SQ — arbitrary names, 7-point Likert, REVERSE handling

**Files:**
- Modify: `lib/qsf_builder.py`
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_qsf_builder.py::test_single_matrix_scale_with_arbitrary_name_and_reverse -v
```
Expected: `assert None is not None`.

- [ ] **Step 3: Implement scale SQ builder**

Append to `lib/qsf_builder.py`:

```python
from lib.qsf import Scale


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
```

In `build_qsf`, after demographics:
```python
for i, s in enumerate(survey.scales, start=1):
    elements.append(_build_scale_sq(survey_id, s, i))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/qsf_builder.py tests/test_qsf_builder.py
git commit -m "feat(qsf): add matrix scale SQ with arbitrary names + REVERSE"
```

---

### Task 7: Multiple matrix scales (1–7 dynamic, mixed arbitrary names)

**Files:**
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the test**

Append:

```python
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
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_qsf_builder.py::test_seven_scales_with_mixed_names_supported tests/test_qsf_builder.py::test_no_scales_produces_zero_scale_sqs -v
```
Expected: 2 passed (loop in Task 6 already handles N).

- [ ] **Step 3: Commit**

```bash
git add tests/test_qsf_builder.py
git commit -m "test(qsf): cover 0..7 scales with mixed arbitrary names"
```

---

### Task 8: Attention check question

**Files:**
- Modify: `lib/qsf_builder.py`
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_qsf_builder.py::test_attention_check_present_when_provided -v
```
Expected: `assert None is not None`.

- [ ] **Step 3: Implement**

Append to `lib/qsf_builder.py`:

```python
from lib.qsf import AttentionCheck


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
```

In `build_qsf`, after scales:
```python
if survey.attention_check is not None:
    elements.append(_build_attention_sq(survey_id, survey.attention_check))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/qsf_builder.py tests/test_qsf_builder.py
git commit -m "feat(qsf): add attention check SQ"
```

---

### Task 9: End SQ with completion code

**Files:**
- Modify: `lib/qsf_builder.py`
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_qsf_builder.py::test_end_question_contains_completion_code -v
```
Expected: `assert None is not None`.

- [ ] **Step 3: Implement**

Append to `lib/qsf_builder.py`:

```python
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
```

In `build_qsf`, after attention:
```python
elements.append(_build_end_sq(survey_id, survey.completion_code))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/qsf_builder.py tests/test_qsf_builder.py
git commit -m "feat(qsf): add end SQ with completion code"
```

---

### Task 10: Survey Blocks element

**Files:**
- Modify: `lib/qsf_builder.py`
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_qsf_builder.py::test_blocks_for_minimal_survey tests/test_qsf_builder.py::test_blocks_with_scales_and_attention -v
```
Expected: failures.

- [ ] **Step 3: Implement**

Append to `lib/qsf_builder.py`:

```python
def _build_blocks(survey_id: str, survey: SurveyInput) -> dict:
    blocks: list[dict] = []
    blocks.append({
        "Type": "Standard",
        "Description": "Consent",
        "ID": "BL_CONSENT",
        "BlockElements": [{"Type": "Question", "QuestionID": "QID_CONSENT"}],
    })
    blocks.append({
        "Type": "Standard",
        "Description": "Demographics",
        "ID": "BL_DEMOGRAPHICS",
        "BlockElements": [
            {"Type": "Question", "QuestionID": f"QID_DEMO_{i}"}
            for i in range(1, len(survey.demographics) + 1)
        ],
    })
    for i, s in enumerate(survey.scales, start=1):
        blocks.append({
            "Type": "Standard",
            "Description": f"{s.name} Scale",
            "ID": f"BL_SCALE_{i}",
            "BlockElements": [{"Type": "Question", "QuestionID": f"QID_SCALE_{i}"}],
        })
    if survey.attention_check is not None:
        blocks.append({
            "Type": "Standard",
            "Description": "Attention Check",
            "ID": "BL_ATTENTION",
            "BlockElements": [{"Type": "Question", "QuestionID": "QID_ATTENTION"}],
        })
    blocks.append({
        "Type": "Standard",
        "Description": "End",
        "ID": "BL_END",
        "BlockElements": [{"Type": "Question", "QuestionID": "QID_END"}],
    })
    return {
        "SurveyID": survey_id,
        "Element": "BL",
        "PrimaryAttribute": "Survey Blocks",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": blocks,
    }
```

Update `build_qsf` (full rewrite — order: BL, SO, SQs):

```python
def build_qsf(survey: SurveyInput) -> dict:
    survey_id = _new_survey_id()
    elements: list[dict] = []
    elements.append(_build_blocks(survey_id, survey))
    elements.append(_build_survey_options(survey_id))
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/qsf_builder.py tests/test_qsf_builder.py
git commit -m "feat(qsf): add Survey Blocks element"
```

---

### Task 11: Survey Flow with PROLIFIC_PID embedded data

**Files:**
- Modify: `lib/qsf_builder.py`
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_qsf_builder.py::test_survey_flow_has_prolific_pid_and_blocks_in_order -v
```
Expected: `assert None is not None`.

- [ ] **Step 3: Implement**

Append to `lib/qsf_builder.py`:

```python
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
```

In `build_qsf`, insert after blocks (order: BL, FL, SO, SQs):

```python
elements.append(_build_blocks(survey_id, survey))
elements.append(_build_flow(survey_id, survey))
elements.append(_build_survey_options(survey_id))
# ... rest unchanged
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_qsf_builder.py -v
```
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/qsf_builder.py tests/test_qsf_builder.py
git commit -m "feat(qsf): add Survey Flow with PROLIFIC_PID embed"
```

---

### Task 12: Bump max scales 5 → 7 in parser

**Files:**
- Modify: `lib/qsf.py`
- Modify: `tests/test_qsf.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_qsf.py`, append:

```python
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
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_qsf.py::test_seven_scales_allowed tests/test_qsf.py::test_eight_scales_rejected -v
```
Expected: `test_seven_scales_allowed` fails (current limit is 5).

- [ ] **Step 3: Bump limit**

In `lib/qsf.py`, locate:

```python
    if len(scales) > 5:
        raise ValueError(
            f"SCALE 은 최대 5개. 입력 {len(scales)}개."
        )
```

Replace with:

```python
    if len(scales) > 7:
        raise ValueError(
            f"SCALE 은 최대 7개. 입력 {len(scales)}개."
        )
```

- [ ] **Step 4: Run**

```bash
pytest tests/test_qsf.py -v
```
Expected: new tests pass; tests referencing "최대 5" may fail (fix in Task 15).

- [ ] **Step 5: Commit**

```bash
git add lib/qsf.py tests/test_qsf.py
git commit -m "feat(qsf): bump max scales 5 -> 7"
```

---

### Task 13: Builder integration test against QSFValidator (0 errors)

**Files:**
- Modify: `tests/test_qsf_builder.py`

- [ ] **Step 1: Write the test**

Append:

```python
from lib.validate import QSFValidator


def _full_survey() -> SurveyInput:
    return SurveyInput(
        title="적응성 연구",
        consent_text="본 연구는 직장인의 변화 적응성을 조사합니다. " * 10,
        demographics=[
            Question(text="연령대?", type="SingleChoice",
                     choices=["20대", "30대", "40대"]),
            Question(text="자유 의견", type="Text", choices=[]),
        ],
        scales=[
            Scale(name="WBI", anchor="7-point Likert",
                  statements=["빠르게 적응한다", "두렵다"], reverse_indices=[2]),
            Scale(name="Resilience", anchor="7-point Likert",
                  statements=["a", "b", "c"], reverse_indices=[]),
        ],
        attention_check=AttentionCheck(text="5번 선택", expected=5),
        completion_code="ABCDEF12",
    )


def test_builder_output_passes_validator_with_zero_errors():
    qsf = build_qsf(_full_survey())
    report = QSFValidator(qsf).run()
    assert report.errors == [], (
        f"errors: {[(e.code, e.message) for e in report.errors]}"
    )
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_qsf_builder.py::test_builder_output_passes_validator_with_zero_errors -v
```
Expected: pass. If errors surface, fix the builder.

- [ ] **Step 3: Commit**

```bash
git add tests/test_qsf_builder.py
git commit -m "test(qsf): integration test builder vs QSFValidator"
```

---

### Task 14: Wire builder into Streamlit page

**Files:**
- Modify: `pages/1_📝_QSF_변환.py`

- [ ] **Step 1: Edit the page**

In `pages/1_📝_QSF_변환.py`, replace this import:

```python
from lib.qsf import parse_text, inject_into_template
```
with:
```python
from lib.qsf import parse_text
from lib.qsf_builder import build_qsf
```

Replace this section:

```python
        survey = parse_text(raw)
        template_path = Path(__file__).parent.parent / "templates" / "standard.qsf"
        with open(template_path, encoding="utf-8") as f:
            template = json.load(f)
        qsf = inject_into_template(survey, template)
        report = QSFValidator(qsf, template=template).run()
```

with:

```python
        survey = parse_text(raw)
        qsf = build_qsf(survey)
        report = QSFValidator(qsf).run()
```

If `json` and `Path` are no longer used in this file, remove them from imports.

- [ ] **Step 2: Smoke test**

```bash
python -m streamlit run Home.py --server.headless true --server.port 8501
```

In a browser, paste the existing PLACEHOLDER content from `pages/1_📝_QSF_변환.py` (or any 3-scale survey) and click "변환 + 검증". Expected: success, 0 errors. Stop the server.

- [ ] **Step 3: Commit**

```bash
git add pages/1_📝_QSF_변환.py
git commit -m "feat(qsf): switch QSF page to dynamic builder"
```

---

### Task 15: Update tests for builder world (before deleting legacy code)

**Files:**
- Modify: `tests/test_qsf.py`
- Modify: `tests/test_validate.py`

- [ ] **Step 1: Identify tests to change**

```bash
grep -n "inject_into_template\|SCALE_SLOTS\|QID_SCALE_AS\|QID_SCALE_RC\|QID_SCALE_ID\|QID_SCALE_DV\|QID_SCALE_HCD\|최대 5" tests/test_qsf.py tests/test_validate.py
```

- [ ] **Step 2: Fix `tests/test_qsf.py`**

- If a test only verifies markdown → `SurveyInput`, keep it but drop any `inject_into_template` calls.
- If a test verifies QSF dict shape with template-specific QIDs (`QID_SCALE_AS`, etc.), delete it — equivalent coverage now lives in `tests/test_qsf_builder.py`.
- Drop tests referencing `SCALE_SLOTS` or `_assign_scales_to_slots`.
- Update tests asserting `"최대 5"` to expect `"최대 7"`.
- Keep parser-only tests (CONSENT empty, DEMO without TYPE, REVERSE indices, etc.).
- Remove now-unused imports (`json`, `inject_into_template`).

- [ ] **Step 3: Fix `tests/test_validate.py`**

Replace `qsf = inject_into_template(survey, template)` with:

```python
from lib.qsf_builder import build_qsf
qsf = build_qsf(survey)
```

Remove `template=template` from `QSFValidator(...)` calls. Delete tests specifically targeting TEMPLATE_DRIFT (no template loaded at runtime).

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```
Expected: all green. `inject_into_template` still in `lib/qsf.py` but no callers.

- [ ] **Step 5: Commit**

```bash
git add tests/test_qsf.py tests/test_validate.py
git commit -m "test: align test_qsf and test_validate with builder"
```

---

### Task 16: Remove legacy injection code from `lib/qsf.py`

**Files:**
- Modify: `lib/qsf.py`

- [ ] **Step 1: Verify nothing references the legacy code**

```bash
grep -rn "inject_into_template\|SCALE_SLOTS\|_assign_scales_to_slots" --include="*.py" .
```
Expected: only matches inside `lib/qsf.py`.

- [ ] **Step 2: Delete dead code**

In `lib/qsf.py`, delete the entire "템플릿 주입" section (from the comment `# ─── 템플릿 주입 ───` down to the `export` function, exclusive). Specifically remove:
- `SCALE_SLOTS` constant
- `LIKERT_7POINT` constant
- `_find_element`, `_find_block`, `_find_question`
- `_question_type_to_qualtrics`
- `_build_demo_question_payload`
- `_assign_scales_to_slots`
- `_inject_consent`, `_inject_demographics`, `_inject_scale`, `_drop_unused_scale_blocks`, `_inject_attention`, `_inject_completion_code`
- `inject_into_template`
- `import copy`

Keep `parse_text`, dataclasses, `export`, parser helpers.

- [ ] **Step 3: Run tests**

```bash
pytest -v
```
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add lib/qsf.py
git commit -m "refactor(qsf): drop template-injection code; builder is sole path"
```

---

### Task 17: Update `docs/input_format_spec.md`

**Files:**
- Modify: `docs/input_format_spec.md`

- [ ] **Step 1: Edit the spec**

In `docs/input_format_spec.md`:

- Replace `- 슬롯 순서: AS, RC, ID, DV, HCD` with `- 척도명(<name>)은 자유롭게 지정 가능 (예: AS, WBI, MyScale).`
- Delete the lines `- <name>이 위 5개 중 하나면 그 슬롯에 매핑` and `- 그 외 이름이면 빈 슬롯에 순서대로 채움`.
- Replace `- SCALE 수는 최대 5개` with `- SCALE 수는 최대 7개`.
- Replace the entire "## 매트릭스 매핑 예시" section with:

```markdown
## 매트릭스 빌드 동작

각 `## SCALE: <name>` 섹션마다 매트릭스 질문 1개와 블록 1개가 생성됩니다.
DataExportTag 는 등장 순서대로 `Q_SCALE_1`, `Q_SCALE_2`, ... 로 부여되며,
`<name>` 은 QuestionDescription 에만 사용되어 한국어를 포함한 임의 문자열을
허용합니다 (예: `AS Scale`, `WBI Scale`, `회복탄력성 Scale`).
```

- [ ] **Step 2: Commit**

```bash
git add docs/input_format_spec.md
git commit -m "docs: update input format spec for dynamic scale names"
```

---

### Task 18: Phase 1 wrap-up — full pytest, manual smoke

- [ ] **Step 1: Full test run**

```bash
pytest -v --tb=short
```
Expected: 100% pass.

- [ ] **Step 2: Manual smoke**

```bash
python -m streamlit run Home.py --server.headless true --server.port 8501
```

In browser, paste a 7-scale survey with mixed names (English + Korean), confirm "변환 + 검증" returns 0 errors. Stop server.

- [ ] **Step 3: Tag Phase 1**

```bash
git tag phase-1-dynamic-builder
```

Phase 1 complete. App ships fully functional without LLM dependency.

---

## Phase 2 — LLM Freeform Normalization

After Phase 2 ships: settings page accepts API key, freeform-text expander on QSF page calls LLM (which picks scale names freely up to 7 scales) and pre-fills the markdown textarea.

### Task 19: `lib/secrets.py` keyring wrapper

**Files:**
- Create: `lib/secrets.py`
- Create: `tests/test_secrets.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_secrets.py`:

```python
"""Tests for lib.secrets — keyring wrapper for LLM API key."""

from __future__ import annotations

from unittest.mock import patch

from lib import secrets as sec


def test_set_and_get_roundtrip():
    fake_store: dict[tuple[str, str], str] = {}

    def fake_set(service, user, value):
        fake_store[(service, user)] = value

    def fake_get(service, user):
        return fake_store.get((service, user))

    with patch("lib.secrets.keyring.set_password", side_effect=fake_set), \
         patch("lib.secrets.keyring.get_password", side_effect=fake_get):
        sec.set_llm_api_key("sk-ant-xxx")
        assert sec.get_llm_api_key() == "sk-ant-xxx"


def test_get_returns_none_when_absent():
    with patch("lib.secrets.keyring.get_password", return_value=None):
        assert sec.get_llm_api_key() is None


def test_delete_swallows_password_delete_error():
    import keyring.errors

    def fake_del(service, user):
        raise keyring.errors.PasswordDeleteError("not found")

    with patch("lib.secrets.keyring.delete_password", side_effect=fake_del):
        sec.delete_llm_api_key()  # should not raise
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_secrets.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `lib/secrets.py`:

```python
"""OS-keyring wrapper for the LLM API key."""

from __future__ import annotations

import keyring
import keyring.errors

_SERVICE = "prolific_qualtrics_vibe_survey"
_USER = "llm_api_key"


def set_llm_api_key(key: str) -> None:
    keyring.set_password(_SERVICE, _USER, key)


def get_llm_api_key() -> str | None:
    return keyring.get_password(_SERVICE, _USER)


def delete_llm_api_key() -> None:
    try:
        keyring.delete_password(_SERVICE, _USER)
    except keyring.errors.PasswordDeleteError:
        pass
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_secrets.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/secrets.py tests/test_secrets.py
git commit -m "feat(secrets): add keyring wrapper for LLM API key"
```

---

### Task 20: `lib/llm.py` — provider detection + `LLMError`

**Files:**
- Create: `lib/llm.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_llm.py`:

```python
"""Tests for lib.llm."""

from __future__ import annotations

import pytest

from lib.llm import LLMError, detect_provider


def test_detect_anthropic_from_prefix():
    assert detect_provider("sk-ant-abc123") == "anthropic"


def test_detect_openai_from_prefix():
    assert detect_provider("sk-proj-xyz") == "openai"
    assert detect_provider("sk-abc123") == "openai"


def test_detect_unknown_raises():
    with pytest.raises(LLMError, match="provider"):
        detect_provider("invalid-key-format")
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_llm.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement skeleton**

Create `lib/llm.py`:

```python
"""LLM provider abstraction (Anthropic + OpenAI).

Auto-detects provider from API-key prefix. Single public function:
    freeform_to_markdown(text, api_key, provider_override=None) -> str
"""

from __future__ import annotations

from typing import Literal

Provider = Literal["anthropic", "openai"]


class LLMError(Exception):
    """LLM call failed (network, quota, parse, or unknown provider)."""


def detect_provider(api_key: str) -> Provider:
    if api_key.startswith("sk-ant-"):
        return "anthropic"
    if api_key.startswith("sk-"):
        return "openai"
    raise LLMError(
        f"Unknown LLM provider for key starting with '{api_key[:8]}...'. "
        "Anthropic keys start with 'sk-ant-', OpenAI keys with 'sk-'."
    )
```

- [ ] **Step 4: Run**

```bash
pytest tests/test_llm.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/llm.py tests/test_llm.py
git commit -m "feat(llm): provider detection from key prefix"
```

---

### Task 21: System prompt + Anthropic `freeform_to_markdown`

**Files:**
- Modify: `lib/llm.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_llm.py`:

```python
from unittest.mock import MagicMock, patch

from lib.llm import freeform_to_markdown


def test_anthropic_freeform_call_returns_markdown():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="# SURVEY: 회복탄력성\n\n## CONSENT\n...")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("lib.llm.anthropic.Anthropic", return_value=mock_client):
        out = freeform_to_markdown(
            "회복탄력성에 대한 7점 척도 5문항 설문 만들어줘.",
            api_key="sk-ant-test",
        )

    assert out.startswith("# SURVEY:")
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5"
    assert call_kwargs["max_tokens"] >= 2000
    system = call_kwargs["system"]
    assert "# SURVEY:" in system
    assert "최대 7" in system  # max-7 constraint
    assert "임의" in system or "freely" in system or "any short label" in system  # name freedom


def test_freeform_empty_input_raises():
    with pytest.raises(LLMError, match="비어"):
        freeform_to_markdown("   ", api_key="sk-ant-test")
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_llm.py::test_anthropic_freeform_call_returns_markdown tests/test_llm.py::test_freeform_empty_input_raises -v
```
Expected: ImportError.

- [ ] **Step 3: Implement**

Append to `lib/llm.py`:

```python
import anthropic

_ANTHROPIC_MODEL = "claude-haiku-4-5"
_OPENAI_MODEL = "gpt-4.1-mini"

_SYSTEM_PROMPT = """You are a survey-design assistant. Convert the user's freeform Korean
or English description of a research survey into the EXACT markdown format below.
Output ONLY the markdown — no explanation, no code fences, no prose around it.

Format:
# SURVEY: <title>

## CONSENT
<one or more paragraphs of informed consent text, ≥100 chars>

## DEMOGRAPHICS
Q: <question>
TYPE: SingleChoice | MultiChoice | Text
- <choice>
- <choice>
(repeat blocks; TYPE: Text omits the dash list)

## SCALE: <name>
ANCHOR: <e.g. 7-point Likert (전혀 동의하지 않는다 ~ 매우 동의한다)>
- <statement>
- <statement> [REVERSE]
(repeat blocks)

## ATTENTION_CHECK
TEXT: <instruction>
EXPECTED: <integer>

## END
COMPLETION_CODE: <6+ char alphanumeric>

Hard constraints:
- Maximum 7 SCALE sections (8+ is a parse error). 최대 7개.
- Pick each scale's <name> freely to fit the survey topic — any short label
  works (any short label like AS, WBI, Resilience, MyScale, 회복탄력성, etc.).
  The name should be a meaningful abbreviation or term, not generic ("Scale1").
  임의의 짧은 레이블을 자유롭게 지정하세요.
- TYPE values must be exactly: SingleChoice, MultiChoice, or Text.
- Append [REVERSE] only on reverse-coded scale items.
- ATTENTION_CHECK is optional; omit it entirely if not requested.
- Default ANCHOR is "7-point Likert (전혀 동의하지 않는다 ~ 매우 동의한다)".
- Match the user's language (Korean or English) for question text.
- COMPLETION_CODE must be 6+ alphanumeric characters with no spaces.
"""


def _call_anthropic(api_key: str, user_text: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=4000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_text}],
    )
    parts = [block.text for block in msg.content if hasattr(block, "text")]
    return "".join(parts).strip()


def freeform_to_markdown(
    text: str,
    api_key: str,
    provider_override: Provider | None = None,
) -> str:
    if not text or not text.strip():
        raise LLMError("입력 텍스트가 비어 있습니다.")
    provider = provider_override or detect_provider(api_key)
    if provider == "anthropic":
        return _call_anthropic(api_key, text)
    raise LLMError(f"Provider '{provider}' not yet implemented.")
```

- [ ] **Step 4: Run**

```bash
pytest tests/test_llm.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/llm.py tests/test_llm.py
git commit -m "feat(llm): anthropic freeform_to_markdown with free naming"
```

---

### Task 22: OpenAI path + provider override

**Files:**
- Modify: `lib/llm.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_openai_freeform_call_returns_markdown():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="# SURVEY: foo\n## CONSENT\n..."))]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("lib.llm.OpenAI", return_value=mock_client):
        out = freeform_to_markdown("survey about X", api_key="sk-proj-test")

    assert out.startswith("# SURVEY:")
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4.1-mini"
    msgs = call_kwargs["messages"]
    assert msgs[0]["role"] == "system"
    assert "# SURVEY:" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"


def test_provider_override_forces_provider():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="# SURVEY: x"))]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("lib.llm.OpenAI", return_value=mock_client):
        out = freeform_to_markdown(
            "x",
            api_key="sk-ant-actually-anthropic",
            provider_override="openai",
        )
    assert out == "# SURVEY: x"
    assert mock_client.chat.completions.create.called
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_llm.py::test_openai_freeform_call_returns_markdown tests/test_llm.py::test_provider_override_forces_provider -v
```
Expected: failures.

- [ ] **Step 3: Implement**

In `lib/llm.py`, add (next to `import anthropic`):

```python
from openai import OpenAI


def _call_openai(api_key: str, user_text: str) -> str:
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=_OPENAI_MODEL,
        max_tokens=4000,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    return (resp.choices[0].message.content or "").strip()
```

In `freeform_to_markdown`, replace the trailing block:

```python
    if provider == "anthropic":
        return _call_anthropic(api_key, text)
    raise LLMError(f"Provider '{provider}' not yet implemented.")
```

with:

```python
    if provider == "anthropic":
        return _call_anthropic(api_key, text)
    if provider == "openai":
        return _call_openai(api_key, text)
    raise LLMError(f"Provider '{provider}' not implemented.")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_llm.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/llm.py tests/test_llm.py
git commit -m "feat(llm): openai freeform_to_markdown + provider override"
```

---

### Task 23: 1-retry error handling

**Files:**
- Modify: `lib/llm.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_anthropic_retries_once_then_raises_llm_error():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        Exception("boom"),
        Exception("boom again"),
    ]
    with patch("lib.llm.anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(LLMError, match="boom again"):
            freeform_to_markdown("x", api_key="sk-ant-test")
    assert mock_client.messages.create.call_count == 2


def test_anthropic_succeeds_on_second_attempt():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="# SURVEY: ok")]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [Exception("transient"), mock_msg]
    with patch("lib.llm.anthropic.Anthropic", return_value=mock_client):
        out = freeform_to_markdown("x", api_key="sk-ant-test")
    assert out == "# SURVEY: ok"
    assert mock_client.messages.create.call_count == 2


def test_openai_also_retries_once():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        Exception("first"),
        Exception("second"),
    ]
    with patch("lib.llm.OpenAI", return_value=mock_client):
        with pytest.raises(LLMError, match="second"):
            freeform_to_markdown("x", api_key="sk-proj-test")
    assert mock_client.chat.completions.create.call_count == 2
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_llm.py -v -k retry
```
Expected: failures.

- [ ] **Step 3: Implement retry wrapper**

In `lib/llm.py`, REPLACE the `freeform_to_markdown` function with this final version (and add `_with_retry` helper above it):

```python
def _with_retry(fn, *args):
    last_exc: Exception | None = None
    for _ in range(2):  # initial + 1 retry
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001
            last_exc = e
    raise LLMError(str(last_exc))


def freeform_to_markdown(
    text: str,
    api_key: str,
    provider_override: Provider | None = None,
) -> str:
    if not text or not text.strip():
        raise LLMError("입력 텍스트가 비어 있습니다.")
    provider = provider_override or detect_provider(api_key)
    if provider == "anthropic":
        return _with_retry(_call_anthropic, api_key, text)
    if provider == "openai":
        return _with_retry(_call_openai, api_key, text)
    raise LLMError(f"Provider '{provider}' not implemented.")
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/test_llm.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add lib/llm.py tests/test_llm.py
git commit -m "feat(llm): single retry then raise LLMError"
```

---

### Task 24: `shared/state.py` — LLM session keys

**Files:**
- Modify: `shared/state.py`

- [ ] **Step 1: Edit**

Open `shared/state.py`. After `PROLIFIC_API_KEY = "prolific_api_key"`, add:

```python
LLM_API_KEY = "llm_api_key"
LLM_PROVIDER_OVERRIDE = "llm_provider_override"
```

In the `DEFAULTS` dict, add the two new keys:

```python
DEFAULTS: dict[str, Any] = {
    COMPLETION_CODE: "",
    STUDY_TITLE: "",
    EXPECTED_MINUTES: 8,
    SCALES_SUMMARY: None,
    PROLIFIC_API_KEY: None,
    LLM_API_KEY: None,
    LLM_PROVIDER_OVERRIDE: None,
}
```

- [ ] **Step 2: Verify**

```bash
pytest -v
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add shared/state.py
git commit -m "feat(state): add LLM_API_KEY and provider override session keys"
```

---

### Task 25: Settings page `pages/0_⚙️_설정.py`

**Files:**
- Create: `pages/0_⚙️_설정.py`

- [ ] **Step 1: Create the page**

Create `pages/0_⚙️_설정.py`:

```python
"""LLM API key management. Stores in OS keyring; auto-detects provider from prefix."""

from __future__ import annotations

import streamlit as st

from lib import secrets as sec
from lib.llm import LLMError, detect_provider
from shared import state


state.init()
st.title("⚙️ 설정")

st.subheader("LLM API Key")
st.caption(
    "자유형 텍스트 → 설문 마크다운 변환에 사용됩니다. "
    "Anthropic 키(`sk-ant-...`) 또는 OpenAI 키(`sk-...`)를 입력하세요. "
    "키는 OS keyring에 저장되며 평문 파일로 남지 않습니다."
)

current = sec.get_llm_api_key()
masked = ("•" * 8 + current[-4:]) if current else "(없음)"
st.write(f"현재 저장된 키: `{masked}`")

new_key = st.text_input("API Key 입력", type="password", key="llm_key_input")
col1, col2 = st.columns(2)
with col1:
    if st.button("저장", type="primary", disabled=not new_key):
        try:
            provider = detect_provider(new_key)
        except LLMError as e:
            st.error(str(e))
        else:
            sec.set_llm_api_key(new_key)
            state.set_(state.LLM_API_KEY, new_key)
            state.set_(state.LLM_PROVIDER_OVERRIDE, None)
            st.success(f"저장됨. 감지된 provider: **{provider}**")
            st.rerun()
with col2:
    if st.button("삭제", disabled=current is None):
        sec.delete_llm_api_key()
        state.set_(state.LLM_API_KEY, None)
        st.success("삭제됨.")
        st.rerun()

st.divider()
st.subheader("Provider 수동 override (선택)")
options = [None, "anthropic", "openai"]
override = st.selectbox(
    "프로바이더",
    options=options,
    format_func=lambda x: "자동 감지" if x is None else x,
    index=options.index(state.get(state.LLM_PROVIDER_OVERRIDE, None)),
)
if override != state.get(state.LLM_PROVIDER_OVERRIDE):
    state.set_(state.LLM_PROVIDER_OVERRIDE, override)
    st.info(f"override = {override or '자동 감지'}")
```

- [ ] **Step 2: Smoke test**

```bash
python -m streamlit run Home.py --server.headless true --server.port 8501
```

- Open the new "설정" page.
- Enter a fake `sk-ant-test1234` key, click 저장. Expect "감지된 provider: **anthropic**".
- Click 삭제. Expect masked display reverts to `(없음)`.

Stop the server.

- [ ] **Step 3: Commit**

```bash
git add pages/0_⚙️_설정.py
git commit -m "feat(ui): add settings page for LLM API key"
```

---

### Task 26: Freeform-text expander on QSF page

**Files:**
- Modify: `pages/1_📝_QSF_변환.py`

- [ ] **Step 1: Edit the page**

After existing imports, add:

```python
from lib import secrets as sec
from lib.llm import LLMError, freeform_to_markdown
```

Just above the existing `raw = st.text_area(...)` line, insert:

```python
with st.expander("✨ 자유형 텍스트로 시작 (LLM 정규화)", expanded=False):
    st.caption(
        "원하는 설문을 자유롭게 적으면 LLM이 위 마크다운 형식으로 변환합니다. "
        "LLM이 척도명도 설문 주제에 맞게 자유롭게 지정합니다 (최대 7개). "
        "변환 결과는 textarea에 채워지며 직접 편집 가능합니다."
    )
    api_key = sec.get_llm_api_key()
    if not api_key:
        st.warning(
            "API Key가 설정되어 있지 않습니다. 좌측 메뉴 '설정' 페이지에서 등록하세요."
        )
    freeform = st.text_area(
        "자유형 텍스트",
        height=200,
        placeholder=(
            "예: 직장인 회복탄력성을 7점 척도로 측정. "
            "회복탄력성·적응성·인내심 척도, 인구통계 3개, 주의검사 포함."
        ),
        key="freeform_input",
    )
    if st.button(
        "LLM으로 변환",
        disabled=not (api_key and freeform.strip()),
        key="llm_convert_btn",
    ):
        with st.spinner("LLM 호출 중..."):
            try:
                md = freeform_to_markdown(
                    freeform,
                    api_key=api_key,
                    provider_override=state.get(state.LLM_PROVIDER_OVERRIDE),
                )
            except LLMError as e:
                st.error(f"LLM 호출 실패: {e}")
            else:
                st.session_state["llm_generated_markdown"] = md
                st.success(
                    "변환 완료. 아래 textarea에 채워졌습니다. "
                    "검토 후 '변환 + 검증'을 누르세요."
                )
                st.rerun()
```

Modify the `raw = st.text_area(...)` line to seed from session state:

```python
raw = st.text_area(
    "설문 텍스트 붙여넣기",
    value=st.session_state.get("llm_generated_markdown", ""),
    height=400,
    placeholder=PLACEHOLDER,
)
```

- [ ] **Step 2: Smoke test (no key path)**

```bash
python -m streamlit run Home.py --server.headless true --server.port 8501
```

- Open QSF page, expand the new section.
- Without a key, button stays disabled, warning shows.

Stop server.

- [ ] **Step 3: Smoke test (with real key, optional)**

If a real API key is registered:
- Paste `"7점 척도 회복탄력성 5문항으로 한국어 설문 만들어줘. 인구통계 2개, 주의검사 포함."`.
- Click "LLM으로 변환".
- Verify scale name in output is meaningful (not `Scale1`).
- Click "변환 + 검증" → 0 errors.

Stop server.

- [ ] **Step 4: Commit**

```bash
git add pages/1_📝_QSF_변환.py
git commit -m "feat(ui): add freeform-text LLM normalizer to QSF page"
```

---

### Task 27: Phase 2 wrap-up — docs + tag

**Files:**
- Modify: `docs/input_format_spec.md`

- [ ] **Step 1: Append LLM workflow section**

Append to `docs/input_format_spec.md`:

```markdown
## 자유형 텍스트 보조 (선택)

설문 페이지의 "✨ 자유형 텍스트로 시작 (LLM 정규화)" expander에 자연어로 설문 요구를
적으면 LLM이 이 양식으로 변환합니다. LLM은 설문 주제에 맞게 척도명도 자유롭게
선택합니다 (최대 7개). 변환 결과는 textarea 에 노출되어 사용자가 직접 검토·편집할
수 있습니다 (human-in-the-loop).

지원 provider:
- Anthropic (`claude-haiku-4-5`) — `sk-ant-` 프리픽스로 자동 감지
- OpenAI (`gpt-4.1-mini`) — `sk-` 프리픽스로 자동 감지

API Key 등록은 좌측 메뉴 "설정" 페이지에서 합니다. 키는 OS keyring에 저장됩니다.
```

- [ ] **Step 2: Run full test suite**

```bash
pytest -v --tb=short
```
Expected: 100% pass.

- [ ] **Step 3: Commit and tag**

```bash
git add docs/input_format_spec.md
git commit -m "docs: note LLM freeform normalizer in input spec"
git tag phase-2-llm-freeform
```

Done. Phase 1 ships dynamic 1–7 scale builder with arbitrary names; Phase 2 adds optional LLM freeform input that picks scale names freely.
