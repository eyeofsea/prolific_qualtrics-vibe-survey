"""QSF parser, template injector, exporter.

학생 마크다운 텍스트 → SurveyInput → 표준 QSF 템플릿에 주입 → 파일 저장.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


# ─── 데이터 모델 ────────────────────────────────────────────────

class Question(BaseModel):
    text: str
    type: Literal["SingleChoice", "MultiChoice", "Text"]
    choices: list[str] = []


class Scale(BaseModel):
    name: str
    anchor: str
    statements: list[str]
    reverse_indices: list[int]


class AttentionCheck(BaseModel):
    text: str
    expected: int


class SurveyInput(BaseModel):
    title: str
    consent_text: str
    demographics: list[Question]
    scales: list[Scale]
    attention_check: AttentionCheck | None
    completion_code: str


# ─── 파서 ──────────────────────────────────────────────────────

SCALE_SLOTS = ["AS", "RC", "ID", "DV", "HCD"]
TYPE_MAP = {
    "SingleChoice": "SingleChoice",
    "MultiChoice": "MultiChoice",
    "Text": "Text",
}


def _split_sections(raw: str) -> list[tuple[str, list[str]]]:
    """`## HEADER` 단위로 분할. 각 섹션의 (header, body_lines) 반환."""
    sections: list[tuple[str, list[str]]] = []
    current_header: str | None = None
    current_body: list[str] = []
    for line in raw.splitlines():
        if line.startswith("## "):
            if current_header is not None:
                sections.append((current_header, current_body))
            current_header = line[3:].strip()
            current_body = []
        else:
            if current_header is not None:
                current_body.append(line)
    if current_header is not None:
        sections.append((current_header, current_body))
    return sections


def _parse_demographics(body: list[str]) -> list[Question]:
    """`Q:`/`TYPE:`/`- choice` 반복 → list[Question]."""
    questions: list[Question] = []
    text: str | None = None
    qtype: str | None = None
    choices: list[str] = []

    def flush():
        nonlocal text, qtype, choices
        if text is None:
            return
        if qtype is None:
            raise ValueError(
                f"DEMOGRAPHICS 질문 '{text}' 에 TYPE: 가 없음. "
                "예시: TYPE: SingleChoice"
            )
        if qtype not in TYPE_MAP:
            raise ValueError(
                f"DEMOGRAPHICS 질문 '{text}' 의 TYPE 이 알 수 없음: '{qtype}'. "
                f"허용: {list(TYPE_MAP)}"
            )
        questions.append(Question(text=text, type=qtype, choices=list(choices)))
        text = None
        qtype = None
        choices = []

    for raw_line in body:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Q:"):
            flush()
            text = line[2:].strip()
        elif line.startswith("TYPE:"):
            qtype = line[5:].strip()
        elif line.startswith("- "):
            choices.append(line[2:].strip())
    flush()
    return questions


REVERSE_RE = re.compile(r"\s*\[REVERSE\]\s*$", re.IGNORECASE)


def _parse_scale(scale_name: str, body: list[str]) -> Scale:
    """`ANCHOR:` 한 줄과 `- statement` 반복 → Scale."""
    anchor = ""
    statements: list[str] = []
    reverse_indices: list[int] = []

    for raw_line in body:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("ANCHOR:"):
            anchor = line[7:].strip()
        elif line.startswith("- "):
            stmt = line[2:].strip()
            if REVERSE_RE.search(stmt):
                stmt = REVERSE_RE.sub("", stmt).rstrip()
                reverse_indices.append(len(statements) + 1)
            statements.append(stmt)

    if not anchor:
        raise ValueError(
            f"SCALE '{scale_name}' 에 ANCHOR: 가 없음. "
            "예시: ANCHOR: 7-point Likert"
        )
    if not statements:
        raise ValueError(
            f"SCALE '{scale_name}' 에 진술이 하나도 없음. "
            "예시: - 나는 변화에 빠르게 적응한다."
        )
    return Scale(
        name=scale_name,
        anchor=anchor,
        statements=statements,
        reverse_indices=reverse_indices,
    )


def _parse_attention(body: list[str]) -> AttentionCheck:
    text = ""
    expected: int | None = None
    for raw_line in body:
        line = raw_line.strip()
        if line.startswith("TEXT:"):
            text = line[5:].strip()
        elif line.startswith("EXPECTED:"):
            value = line[9:].strip()
            try:
                expected = int(value)
            except ValueError:
                raise ValueError(
                    f"ATTENTION_CHECK 의 EXPECTED 가 정수가 아님: '{value}'"
                )
    if not text:
        raise ValueError("ATTENTION_CHECK 에 TEXT: 가 없음.")
    if expected is None:
        raise ValueError("ATTENTION_CHECK 에 EXPECTED: 가 없음.")
    return AttentionCheck(text=text, expected=expected)


def _parse_end(body: list[str]) -> str:
    for raw_line in body:
        line = raw_line.strip()
        if line.startswith("COMPLETION_CODE:"):
            return line[len("COMPLETION_CODE:"):].strip()
    raise ValueError("END 섹션에 COMPLETION_CODE: 가 없음.")


def parse_text(raw: str) -> SurveyInput:
    """학생 마크다운 → SurveyInput. 파싱 실패 시 ValueError."""
    if not raw or not raw.strip():
        raise ValueError("입력이 비어 있음.")

    title_match = re.search(r"^#\s*SURVEY:\s*(.+)$", raw, re.MULTILINE)
    if not title_match:
        raise ValueError(
            "첫 줄에 '# SURVEY: <제목>' 헤더가 필요함."
        )
    title = title_match.group(1).strip()

    sections = _split_sections(raw)
    if not sections:
        raise ValueError("'## CONSENT' 등 섹션이 하나도 없음.")

    consent_text = ""
    demographics: list[Question] = []
    scales: list[Scale] = []
    attention: AttentionCheck | None = None
    completion_code = ""

    for header, body in sections:
        if header == "CONSENT":
            consent_text = "\n".join(body).strip()
        elif header == "DEMOGRAPHICS":
            demographics = _parse_demographics(body)
        elif header.startswith("SCALE:"):
            scale_name = header[6:].strip()
            scales.append(_parse_scale(scale_name, body))
        elif header == "ATTENTION_CHECK":
            attention = _parse_attention(body)
        elif header == "END":
            completion_code = _parse_end(body)

    if len(scales) > 7:
        raise ValueError(
            f"SCALE 은 최대 7개. 입력 {len(scales)}개."
        )
    if not consent_text:
        raise ValueError("'## CONSENT' 섹션이 비어 있음.")
    if not completion_code:
        raise ValueError("'## END' 섹션의 COMPLETION_CODE 누락.")

    return SurveyInput(
        title=title,
        consent_text=consent_text,
        demographics=demographics,
        scales=scales,
        attention_check=attention,
        completion_code=completion_code,
    )


# ─── 템플릿 주입 ───────────────────────────────────────────────

LIKERT_7POINT = [
    "전혀 동의하지 않는다",
    "동의하지 않는다",
    "약간 동의하지 않는다",
    "보통이다",
    "약간 동의한다",
    "동의한다",
    "매우 동의한다",
]


def _find_element(qsf: dict, element: str, primary: str) -> dict | None:
    for el in qsf.get("SurveyElements", []):
        if el.get("Element") == element and el.get("PrimaryAttribute") == primary:
            return el
    return None


def _find_block(blocks_payload: list[dict], block_id: str) -> dict | None:
    for b in blocks_payload:
        if b.get("ID") == block_id:
            return b
    return None


def _find_question(qsf: dict, qid: str) -> dict | None:
    for el in qsf.get("SurveyElements", []):
        if el.get("Element") == "SQ" and el.get("PrimaryAttribute") == qid:
            return el
    return None


def _question_type_to_qualtrics(qtype: str) -> tuple[str, str, str | None]:
    """SingleChoice/MultiChoice/Text → (QuestionType, Selector, SubSelector)."""
    if qtype == "SingleChoice":
        return ("MC", "SAVR", "TX")
    if qtype == "MultiChoice":
        return ("MC", "MAVR", "TX")
    if qtype == "Text":
        return ("TE", "SL", None)
    raise ValueError(f"알 수 없는 type: {qtype}")


def _build_demo_question_payload(qid: str, q: Question, idx: int) -> dict:
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
        payload["Choices"] = {str(i + 1): {"Display": c} for i, c in enumerate(q.choices)}
        payload["ChoiceOrder"] = [str(i + 1) for i in range(len(q.choices))]
    return payload


def _assign_scales_to_slots(scales: list[Scale]) -> dict[str, Scale]:
    """학생 SCALE 입력 → 템플릿 슬롯(AS/RC/ID/DV/HCD) 매핑."""
    assigned: dict[str, Scale] = {}
    leftover: list[Scale] = []
    for s in scales:
        if s.name in SCALE_SLOTS and s.name not in assigned:
            assigned[s.name] = s
        else:
            leftover.append(s)
    free_slots = [k for k in SCALE_SLOTS if k not in assigned]
    for s in leftover:
        if not free_slots:
            raise ValueError(
                f"SCALE 슬롯({SCALE_SLOTS}) 초과: '{s.name}' 매핑 불가."
            )
        slot = free_slots.pop(0)
        assigned[slot] = s
    return assigned


def _inject_consent(qsf: dict, consent_text: str) -> None:
    elem = _find_question(qsf, "QID_CONSENT_1")
    if elem is None:
        return
    elem["Payload"]["QuestionText"] = consent_text


def _inject_demographics(qsf: dict, demographics: list[Question]) -> None:
    blocks_elem = _find_element(qsf, "BL", "Survey Blocks")
    if blocks_elem is None:
        return
    demo_block = _find_block(blocks_elem["Payload"], "BL_DEMOGRAPHICS")
    if demo_block is None:
        return

    # 기존 DEMO QID 목록
    old_qids = [
        e["QuestionID"]
        for e in demo_block.get("BlockElements", [])
        if e.get("Type") == "Question"
    ]
    # SurveyElements 에서 기존 demo SQ 제거
    qsf["SurveyElements"] = [
        e
        for e in qsf["SurveyElements"]
        if not (e.get("Element") == "SQ" and e.get("PrimaryAttribute") in old_qids)
    ]

    new_block_elements = []
    for i, q in enumerate(demographics, start=1):
        qid = f"QID_DEMO_{i}"
        new_block_elements.append({"Type": "Question", "QuestionID": qid})
        qsf["SurveyElements"].append({
            "SurveyID": qsf["SurveyEntry"]["SurveyID"],
            "Element": "SQ",
            "PrimaryAttribute": qid,
            "SecondaryAttribute": q.text[:60],
            "TertiaryAttribute": None,
            "Payload": _build_demo_question_payload(qid, q, i),
        })
    demo_block["BlockElements"] = new_block_elements


def _inject_scale(qsf: dict, slot: str, scale: Scale) -> None:
    qid = f"QID_SCALE_{slot}"
    elem = _find_question(qsf, qid)
    if elem is None:
        return
    payload = elem["Payload"]
    # statements → Choices
    payload["Choices"] = {
        str(i + 1): {"Display": s} for i, s in enumerate(scale.statements)
    }
    payload["ChoiceOrder"] = [str(i + 1) for i in range(len(scale.statements))]
    # 7-point Likert anchor 유지 (이미 Answers 7개)
    if "7" in scale.anchor.lower() or "likert" in scale.anchor.lower():
        if "Answers" not in payload or len(payload.get("Answers", {})) != 7:
            payload["Answers"] = {
                str(i + 1): {"Display": LIKERT_7POINT[i]} for i in range(7)
            }
            payload["AnswerOrder"] = [str(i + 1) for i in range(7)]
    payload["QuestionDescription"] = f"{slot} Scale"
    if scale.reverse_indices:
        invalid = [i for i in scale.reverse_indices if i < 1 or i > len(scale.statements)]
        if invalid:
            raise ValueError(
                f"SCALE '{scale.name}' REVERSE index 범위 초과: {invalid} "
                f"(statements {len(scale.statements)}개)"
            )
        payload["RecodeValues"] = {
            str(i): str(8 - i) if i in scale.reverse_indices else str(i)
            for i in range(1, len(scale.statements) + 1)
        }


def _drop_unused_scale_blocks(qsf: dict, used_slots: set[str]) -> None:
    """매핑 안 된 매트릭스 슬롯의 블록·질문을 SurveyElements/Survey Flow에서 제거."""
    blocks_elem = _find_element(qsf, "BL", "Survey Blocks")
    flow_elem = _find_element(qsf, "FL", "Survey Flow")
    if blocks_elem is None or flow_elem is None:
        return

    unused = [s for s in SCALE_SLOTS if s not in used_slots]
    unused_block_ids = {f"BL_SCALE_{s}" for s in unused}
    unused_qids = {f"QID_SCALE_{s}" for s in unused}

    # 블록 제거
    blocks_elem["Payload"] = [
        b for b in blocks_elem["Payload"] if b.get("ID") not in unused_block_ids
    ]
    # 질문 제거
    qsf["SurveyElements"] = [
        e
        for e in qsf["SurveyElements"]
        if not (e.get("Element") == "SQ" and e.get("PrimaryAttribute") in unused_qids)
    ]
    # Survey Flow 에서 제거
    flow_payload = flow_elem["Payload"]
    flow_payload["Flow"] = [
        f for f in flow_payload.get("Flow", [])
        if not (f.get("Type") == "Standard" and f.get("ID") in unused_block_ids)
    ]


def _inject_attention(qsf: dict, attention: AttentionCheck | None) -> None:
    if attention is None:
        # 블록 + 질문 + 플로우 제거
        blocks_elem = _find_element(qsf, "BL", "Survey Blocks")
        flow_elem = _find_element(qsf, "FL", "Survey Flow")
        if blocks_elem is not None:
            blocks_elem["Payload"] = [
                b for b in blocks_elem["Payload"] if b.get("ID") != "BL_ATTENTION"
            ]
        qsf["SurveyElements"] = [
            e for e in qsf["SurveyElements"]
            if not (e.get("Element") == "SQ" and e.get("PrimaryAttribute") == "QID_ATTENTION")
        ]
        if flow_elem is not None:
            flow_elem["Payload"]["Flow"] = [
                f for f in flow_elem["Payload"].get("Flow", [])
                if not (f.get("Type") == "Standard" and f.get("ID") == "BL_ATTENTION")
            ]
        return
    elem = _find_question(qsf, "QID_ATTENTION")
    if elem is None:
        return
    elem["Payload"]["QuestionText"] = attention.text
    elem["Payload"]["AttentionExpected"] = attention.expected


def _inject_completion_code(qsf: dict, code: str) -> None:
    elem = _find_question(qsf, "QID_END")
    if elem is None:
        return
    text = elem["Payload"].get("QuestionText", "")
    if "COMPLETION_CODE_PLACEHOLDER" in text:
        text = text.replace("COMPLETION_CODE_PLACEHOLDER", code)
    else:
        text = (
            f"설문에 참여해 주셔서 감사합니다.\n\n"
            f"Prolific Completion Code: {code}\n\n"
            f"위 코드를 Prolific에 입력하셔야 보상이 지급됩니다."
        )
    elem["Payload"]["QuestionText"] = text


def inject_into_template(survey: SurveyInput, template: dict) -> dict:
    """표준 QSF 템플릿 dict에 survey 내용 주입.

    원본 template은 변경하지 않고 deepcopy 후 작업.
    """
    qsf = copy.deepcopy(template)

    qsf["SurveyEntry"]["SurveyName"] = survey.title

    _inject_consent(qsf, survey.consent_text)
    _inject_demographics(qsf, survey.demographics)

    assigned = _assign_scales_to_slots(survey.scales)
    for slot, scale in assigned.items():
        _inject_scale(qsf, slot, scale)
    _drop_unused_scale_blocks(qsf, set(assigned.keys()))

    _inject_attention(qsf, survey.attention_check)
    _inject_completion_code(qsf, survey.completion_code)

    return qsf


# ─── 내보내기 ──────────────────────────────────────────────────

def export(qsf: dict, path: str) -> None:
    Path(path).write_text(
        json.dumps(qsf, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
