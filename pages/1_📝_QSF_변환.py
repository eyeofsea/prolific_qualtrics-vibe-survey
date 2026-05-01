import json
from pathlib import Path

import streamlit as st

from lib.qsf import parse_text, inject_into_template
from lib.validate import QSFValidator
from shared import state


state.init()
st.title("📝 QSF 변환·검증")

PLACEHOLDER = """# SURVEY: 적응성·회복탄력성 연구

## CONSENT
본 연구는 직장인의 변화 적응성을 조사합니다. 응답은 익명 처리되며 학술 목적으로만 사용됩니다.
참여는 자발적이며 언제든 중단할 수 있습니다.

## DEMOGRAPHICS
Q: 귀하의 연령대는?
TYPE: SingleChoice
- 19-29세
- 30-39세
- 40-49세
- 50세 이상

## SCALE: AS
ANCHOR: 7-point Likert (전혀 동의하지 않는다 ~ 매우 동의한다)
- 나는 변화에 빠르게 적응한다.
- 새로운 환경이 두렵다. [REVERSE]
- 변화는 기회를 만든다.

## ATTENTION_CHECK
TEXT: 주의 깊게 읽고 있다면 '5번 (약간 동의한다)'을 선택해 주세요.
EXPECTED: 5

## END
COMPLETION_CODE: ABC12345
"""

raw = st.text_area("설문 텍스트 붙여넣기", height=400, placeholder=PLACEHOLDER)

if st.button("변환 + 검증", type="primary"):
    try:
        survey = parse_text(raw)
        template_path = Path(__file__).parent.parent / "templates" / "standard.qsf"
        with open(template_path, encoding="utf-8") as f:
            template = json.load(f)
        qsf = inject_into_template(survey, template)
        report = QSFValidator(qsf, template=template).run()

        st.subheader("검증 리포트")
        if report.is_blocked:
            st.error(f"❌ 오류 {len(report.errors)}개 — 다운로드 막힘")
            for e in report.errors:
                st.write(f"- **{e.code}** ({e.location}): {e.message}")
                if e.suggestion:
                    st.caption(f"  → {e.suggestion}")
        else:
            warns = report.warnings
            infos = report.infos
            if warns:
                st.warning(f"⚠️ 경고 {len(warns)}개 (다운로드 가능)")
                for w in warns:
                    st.write(f"- **{w.code}**: {w.message}")
            if infos:
                with st.expander(f"ℹ️ 정보 {len(infos)}개"):
                    for i in infos:
                        st.write(f"- **{i.code}**: {i.message}")
            if not warns and not infos:
                st.success("✅ 22/22 통과")

            st.divider()
            st.write(f"- 제목: **{survey.title}**")
            st.write(f"- Consent: {len(survey.consent_text)}자")
            st.write(f"- 인구통계 {len(survey.demographics)} 문항")
            total = sum(len(s.statements) for s in survey.scales)
            st.write(f"- 매트릭스 {len(survey.scales)} 척도 (총 {total} 문항)")

            state.from_qsf_to_prolific(survey)

            qsf_bytes = json.dumps(qsf, ensure_ascii=False, indent=2).encode("utf-8")
            safe_name = survey.title.replace(" ", "_").replace("/", "_")
            st.download_button(
                "📥 QSF 다운로드",
                qsf_bytes,
                file_name=f"{safe_name}.qsf",
                mime="application/json",
            )

            st.info(
                "다음: Qualtrics에 임포트 → Survey URL 복사 → "
                "좌측 '🚀 Prolific 제어' 페이지로 이동"
            )
    except ValueError as e:
        st.error(f"파싱 실패: {e}")
    except FileNotFoundError as e:
        st.error(f"템플릿 파일을 찾을 수 없음: {e}")
