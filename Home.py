import streamlit as st

from shared import state


st.set_page_config(page_title="바이브 설문 스튜디오", layout="wide")
state.init()

st.title("🎯 바이브 설문 스튜디오")
st.markdown(
    """
1. **🎓 Qualtrics 실습**: Qualtrics API 로 서베이를 직접 만들고 질문·블록·플로우 관리 (학생 실습용)
2. **🚀 Prolific 제어**: 스터디 생성·모니터링·승인

좌측 사이드바에서 페이지 선택.
"""
)

sid = state.get(state.QUALTRICS_SURVEY_ID)
if sid:
    with st.expander("📌 현재 작업 서베이"):
        st.write(f"**Survey ID**: `{sid}`")
        name = state.get(state.QUALTRICS_SURVEY_NAME)
        if name:
            st.write(f"**이름**: {name}")
