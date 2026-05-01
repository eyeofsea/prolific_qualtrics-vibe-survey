"""Generate a comprehensive test QSF file for manual Qualtrics import verification.

Covers every feature the dynamic builder produces:
- Multiple scales with arbitrary names (English, Korean, mixed)
- A scale with [REVERSE] markers (verify they appear in QuestionDescription only)
- All three demographics types (SingleChoice, MultiChoice, Text)
- Attention check
- PROLIFIC_PID embedded data in Survey Flow
- 7-point Likert anchors with Korean labels

Run:  python scripts/generate_test_qsf.py
Output: ./test_qsf_for_qualtrics.qsf
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.qsf import (
    AttentionCheck,
    Question,
    Scale,
    SurveyInput,
)
from lib.qsf_builder import build_qsf
from lib.qsf import export
from lib.validate import QSFValidator


def make_test_survey() -> SurveyInput:
    return SurveyInput(
        title="QSF 빌더 검증용 테스트 설문 (2026-05)",
        consent_text=(
            "본 설문은 dynamic QSF 빌더의 Qualtrics import 호환성을 검증하기 위한 "
            "테스트입니다. 응답은 익명 처리되며 학술 목적으로만 사용됩니다. "
            "참여는 자발적이며 언제든 중단할 수 있습니다. "
            "문의: 연구자 이메일."
        ),
        demographics=[
            Question(
                text="귀하의 연령대는?",
                type="SingleChoice",
                choices=["19-29세", "30-39세", "40-49세", "50세 이상"],
            ),
            Question(
                text="관심 있는 주제를 모두 고르세요. (복수 선택)",
                type="MultiChoice",
                choices=["AI", "데이터 과학", "심리학", "디자인", "경영"],
            ),
            Question(
                text="자유롭게 한 마디 남겨주세요. (선택 사항)",
                type="Text",
                choices=[],
            ),
        ],
        scales=[
            # English short label
            Scale(
                name="WBI",
                anchor="7-point Likert (전혀 동의하지 않는다 ~ 매우 동의한다)",
                statements=[
                    "직장에서 만족감을 느낀다.",
                    "일과 삶의 균형이 좋다.",
                    "동료와의 관계가 원만하다.",
                ],
                reverse_indices=[],
            ),
            # Korean label, with REVERSE marker on item 2
            Scale(
                name="회복탄력성",
                anchor="7-point Likert",
                statements=[
                    "어려움 속에서도 빠르게 회복한다.",
                    "변화에 흔들린다.",  # [REVERSE]
                    "좌절 후 다시 일어선다.",
                    "스트레스에 쉽게 무너진다.",  # [REVERSE]
                ],
                reverse_indices=[2, 4],
            ),
            # Multi-word English label
            Scale(
                name="Resilience_Trait",
                anchor="7-point Likert",
                statements=[
                    "I bounce back quickly.",
                    "I adapt to new circumstances.",
                ],
                reverse_indices=[],
            ),
        ],
        attention_check=AttentionCheck(
            text="주의 깊게 읽고 있다면 '5번 (약간 동의한다)'을 선택해 주세요.",
            expected=5,
        ),
        completion_code="ABC12345TEST",
    )


def main() -> None:
    survey = make_test_survey()
    qsf = build_qsf(survey)

    report = QSFValidator(qsf).run()
    print(f"Validator: {len(report.errors)} errors, "
          f"{len(report.warnings)} warnings, "
          f"{len(report.infos)} infos")
    if report.errors:
        for e in report.errors:
            print(f"  ERROR {e.code}: {e.message}")
        raise SystemExit(1)
    for w in report.warnings:
        print(f"  WARN  {w.code}: {w.message}")
    for i in report.infos:
        print(f"  INFO  {i.code}: {i.message}")

    out = Path("test_qsf_for_qualtrics.qsf")
    export(qsf, str(out))
    print(f"\nWrote {out.resolve()}")
    print(f"  - {len(survey.scales)} scales: "
          f"{[s.name for s in survey.scales]}")
    print(f"  - reverse markers in scale 2 (회복탄력성): "
          f"items {survey.scales[1].reverse_indices}")
    print(f"  - {len(survey.demographics)} demographics, "
          f"attention check: yes, completion code: {survey.completion_code}")


if __name__ == "__main__":
    main()
