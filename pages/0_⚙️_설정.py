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
            state.set_(state.LLM_PROVIDER_OVERRIDE, None)
            st.success(f"저장됨. 감지된 provider: **{provider}**")
            st.rerun()
with col2:
    if st.button("삭제", disabled=current is None):
        sec.delete_llm_api_key()
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
