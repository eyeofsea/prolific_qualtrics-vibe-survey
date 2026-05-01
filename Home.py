import streamlit as st

from shared import state


st.set_page_config(page_title="바이브 설문 스튜디오", layout="wide")
state.init()

st.title("🎯 바이브 설문 스튜디오")
st.markdown(
    """
1. **📝 QSF 변환**: 설문 텍스트 → 검증된 QSF
2. Qualtrics에 임포트 → Survey URL 받기 (앱 밖)
3. **🚀 Prolific 제어**: 스터디 생성·모니터링·승인

좌측 사이드바에서 페이지 선택.
"""
)

if state.get(state.STUDY_TITLE):
    with st.expander("📌 현재 작업"):
        st.write(f"**스터디**: {state.get(state.STUDY_TITLE)}")
        st.write(f"**Completion Code**: `{state.get(state.COMPLETION_CODE)}`")
        s = state.get(state.SCALES_SUMMARY)
        if s:
            st.write(f"**척도**: {s['n_scales']}개, 총 {s['total_items']} 문항")
