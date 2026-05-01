"""QSF parser and exporter.

학생 마크다운 텍스트 → SurveyInput → (lib.qsf_builder.build_qsf) → 파일 저장.
"""

from __future__ import annotations

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


# ─── 내보내기 ──────────────────────────────────────────────────

def export(qsf: dict, path: str) -> None:
    Path(path).write_text(
        json.dumps(qsf, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
