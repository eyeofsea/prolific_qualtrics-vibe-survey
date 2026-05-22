"""학생용 Qualtrics 서베이 생성 실습 페이지.

수업 흐름:
1. 강사가 .streamlit/secrets.toml 또는 환경변수에 Qualtrics 토큰을 설정.
2. 학생은 서베이를 직접 만들고 (Tab 1), 다양한 유형의 질문을 추가 (Tab 2),
   블록·플로우를 정리 (Tab 3).
3. 페이지 좌상단에 현재 작업 서베이 ID 가 표시되어 실수로 다른 서베이를
   건드리지 않도록 함.
"""

from __future__ import annotations

import os

import streamlit as st

from lib.qualtrics_api import (
    BlockInput,
    LikertMatrixInput,
    MultipleChoiceInput,
    QualtricsClient,
    QualtricsError,
    SurveyConfig,
    TextEntryInput,
)
from shared import state


state.init()
st.set_page_config(page_title="Qualtrics 실습", layout="wide")
st.title("🎓 Qualtrics 서베이 생성 실습")
st.caption(
    "yrvelez/qualtrics-mcp-server 의 핵심 도구를 Streamlit UI 로 옮긴 학생 실습용 페이지."
)


# ─── 인증 ──────────────────────────────────────────────────

def _load_credentials() -> tuple[str | None, str | None]:
    token: str | None = None
    dc: str | None = None
    try:
        if "qualtrics" in st.secrets:
            section = st.secrets["qualtrics"]
            token = section.get("api_token") or None
            dc = section.get("data_center") or None
    except (FileNotFoundError, KeyError, AttributeError):
        pass
    token = token or os.environ.get("QUALTRICS_API_TOKEN")
    dc = dc or os.environ.get("QUALTRICS_DATA_CENTER")
    return token, dc


def _load_app_password() -> str | None:
    """수업용 공유 비밀번호. secrets.toml 의 [auth] password 또는 환경변수."""
    try:
        if "auth" in st.secrets:
            pw = st.secrets["auth"].get("password")
            if pw:
                return str(pw)
    except (FileNotFoundError, KeyError, AttributeError):
        pass
    return os.environ.get("APP_PASSWORD") or None


def _password_gate() -> bool:
    """비밀번호가 설정되어 있으면 입력받아 검증. 없으면 통과."""
    expected = _load_app_password()
    if not expected:
        return True
    if st.session_state.get("auth_ok"):
        return True
    st.subheader("🔐 수업 비밀번호 입력")
    st.caption(
        "강사가 알려준 수업용 비밀번호를 입력하세요. 비밀번호는 한 번만 입력하면 됩니다."
    )
    with st.form("auth_gate"):
        pw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("확인", type="primary"):
            if pw == expected:
                st.session_state["auth_ok"] = True
                st.rerun()
            else:
                st.error("비밀번호가 일치하지 않습니다.")
    return False


if not _password_gate():
    st.stop()


api_token, data_center = _load_credentials()
if not api_token or not data_center:
    st.error(
        "Qualtrics 인증 정보가 없습니다. `.streamlit/secrets.toml` 또는 환경변수에 "
        "`QUALTRICS_API_TOKEN`, `QUALTRICS_DATA_CENTER`(예: `hnd1`)를 설정하세요."
    )
    with st.expander("설정 예시"):
        st.code(
            """# .streamlit/secrets.toml
[qualtrics]
api_token = "YOUR_TOKEN"
data_center = "hnd1"

[auth]
password = "수업용 공유 비밀번호"  # 선택, 설정 시 학생에게 알려준 뒤 입력받음
""",
            language="toml",
        )
        st.code(
            "export QUALTRICS_API_TOKEN=YOUR_TOKEN\n"
            "export QUALTRICS_DATA_CENTER=hnd1\n"
            "export APP_PASSWORD=...",
            language="bash",
        )
    st.stop()


@st.cache_resource(show_spinner=False)
def _client(token: str, dc: str) -> QualtricsClient:
    return QualtricsClient(token, dc)


client = _client(api_token, data_center)


# ─── 현재 작업 서베이 ──────────────────────────────────────

current_sid = state.get(state.QUALTRICS_SURVEY_ID)
current_name = state.get(state.QUALTRICS_SURVEY_NAME)
with st.container(border=True):
    if current_sid:
        c1, c2 = st.columns([3, 1])
        c1.markdown(
            f"**현재 작업 서베이**: `{current_sid}` — {current_name or '(이름 모름)'}"
        )
        if c2.button("선택 해제", use_container_width=True):
            state.set_(state.QUALTRICS_SURVEY_ID, None)
            state.set_(state.QUALTRICS_SURVEY_NAME, None)
            st.rerun()
    else:
        st.info("아래 Tab 1 에서 서베이를 새로 만들거나 기존 서베이를 선택하세요.")


tab1, tab2, tab3 = st.tabs(
    ["1️⃣ 서베이 생성·관리", "2️⃣ 질문 추가", "3️⃣ 블록 & 플로우"]
)


# ─── Tab 1: 서베이 생성·관리 ──────────────────────────

with tab1:
    st.subheader("새 서베이 만들기")
    with st.form("create_survey", clear_on_submit=False):
        new_name = st.text_input("서베이 이름", placeholder="예: 2026 봄학기 실습 서베이")
        lang = st.selectbox(
            "기본 언어", ["EN", "KO", "JA", "ZH-S", "ES"], index=1
        )
        submit_create = st.form_submit_button("서베이 생성", type="primary")
    if submit_create:
        if not new_name.strip():
            st.error("서베이 이름은 필수입니다.")
        else:
            try:
                result = client.create_survey(
                    SurveyConfig(name=new_name.strip(), language=lang)
                )
                sid = result.get("SurveyID") or result.get("id")
                if sid:
                    state.set_(state.QUALTRICS_SURVEY_ID, sid)
                    state.set_(state.QUALTRICS_SURVEY_NAME, new_name.strip())
                    st.success(f"생성 성공: `{sid}`")
                    st.rerun()
                else:
                    st.warning(f"응답에 SurveyID 없음: {result}")
            except QualtricsError as e:
                st.error(f"실패: {e}")

    st.divider()
    st.subheader("내 서베이 목록")
    if st.button("🔄 새로고침"):
        st.rerun()

    try:
        surveys = client.list_surveys()
    except QualtricsError as e:
        st.error(f"목록 조회 실패: {e}")
        surveys = []

    if not surveys:
        st.info("서베이가 없습니다.")
    for s in surveys[:50]:
        sid = s.get("id", "")
        name = s.get("name", "(이름 없음)")
        is_active = s.get("isActive", False)
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 1, 1, 1])
            c1.write(f"**{name}**  \n`{sid}`")
            c2.write("🟢 활성" if is_active else "⚪ 비활성")
            if c3.button("선택", key=f"sel-{sid}"):
                state.set_(state.QUALTRICS_SURVEY_ID, sid)
                state.set_(state.QUALTRICS_SURVEY_NAME, name)
                st.rerun()
            if is_active:
                if c4.button("비활성화", key=f"deact-{sid}"):
                    try:
                        client.deactivate_survey(sid)
                        st.rerun()
                    except QualtricsError as e:
                        st.error(f"실패: {e}")
            else:
                if c4.button("활성화", key=f"act-{sid}"):
                    try:
                        client.activate_survey(sid)
                        st.rerun()
                    except QualtricsError as e:
                        st.error(f"실패: {e}")
            if c5.button("삭제", key=f"del-{sid}"):
                try:
                    client.delete_survey(sid)
                    if current_sid == sid:
                        state.set_(state.QUALTRICS_SURVEY_ID, None)
                        state.set_(state.QUALTRICS_SURVEY_NAME, None)
                    st.rerun()
                except QualtricsError as e:
                    st.error(f"실패: {e}")


def _require_survey() -> str | None:
    sid = state.get(state.QUALTRICS_SURVEY_ID)
    if not sid:
        st.warning("Tab 1 에서 먼저 서베이를 생성하거나 선택하세요.")
        return None
    return sid


# ─── Tab 2: 질문 추가 ─────────────────────────────────

with tab2:
    sid = _require_survey()
    if sid:
        try:
            blocks = client.list_blocks(sid)
        except QualtricsError as e:
            st.error(f"블록 조회 실패: {e}")
            blocks = []

        block_options = ["(기본 블록)"] + [
            f"{b.get('Description', '(이름 없음)')} — {b['id']}" for b in blocks
        ]
        block_choice = st.selectbox("추가할 블록", block_options)
        chosen_block_id: str | None = None
        if block_choice != "(기본 블록)":
            chosen_block_id = block_choice.split(" — ")[-1]

        qtype = st.radio(
            "질문 유형",
            ["객관식 (MC)", "텍스트 (TE)", "Likert 매트릭스"],
            horizontal=True,
        )

        st.divider()

        if qtype == "객관식 (MC)":
            with st.form("add_mc"):
                text = st.text_area("질문 본문", height=80)
                choices_raw = st.text_area(
                    "선택지 (한 줄에 하나)",
                    height=120,
                    placeholder="동의함\n동의하지 않음\n잘 모르겠음",
                )
                col1, col2, col3 = st.columns(3)
                multi = col1.checkbox("다중 선택")
                force = col2.checkbox("응답 강제")
                tag = col3.text_input("DataExportTag (선택)")
                if st.form_submit_button("질문 추가", type="primary"):
                    items = [c.strip() for c in choices_raw.splitlines() if c.strip()]
                    if not text.strip() or len(items) < 2:
                        st.error("질문 본문과 최소 2개 선택지가 필요합니다.")
                    else:
                        try:
                            r = client.add_multiple_choice(
                                sid,
                                MultipleChoiceInput(
                                    text=text.strip(),
                                    choices=items,
                                    multi_select=multi,
                                    force_response=force,
                                    data_export_tag=tag or None,
                                ),
                                block_id=chosen_block_id,
                            )
                            st.success(
                                f"추가됨: QID `{r.get('QuestionID', '?')}`"
                            )
                        except QualtricsError as e:
                            st.error(f"실패: {e}")

        elif qtype == "텍스트 (TE)":
            with st.form("add_te"):
                text = st.text_area("질문 본문", height=80)
                col1, col2, col3 = st.columns(3)
                selector = col1.selectbox(
                    "입력 형식",
                    ["SL (단일 줄)", "ML (여러 줄)", "ESTB (에세이)"],
                )
                force = col2.checkbox("응답 강제")
                tag = col3.text_input("DataExportTag (선택)")
                if st.form_submit_button("질문 추가", type="primary"):
                    if not text.strip():
                        st.error("질문 본문은 필수입니다.")
                    else:
                        try:
                            r = client.add_text_entry(
                                sid,
                                TextEntryInput(
                                    text=text.strip(),
                                    selector=selector.split(" ")[0],  # type: ignore[arg-type]
                                    force_response=force,
                                    data_export_tag=tag or None,
                                ),
                                block_id=chosen_block_id,
                            )
                            st.success(
                                f"추가됨: QID `{r.get('QuestionID', '?')}`"
                            )
                        except QualtricsError as e:
                            st.error(f"실패: {e}")

        else:  # Likert 매트릭스
            with st.form("add_lk"):
                text = st.text_area(
                    "지시문",
                    height=80,
                    placeholder="다음 문항에 대해 동의 정도를 선택해 주세요.",
                )
                statements_raw = st.text_area(
                    "문항 (한 줄에 하나)",
                    height=120,
                    placeholder="나는 변화에 빠르게 적응한다.\n새로운 환경이 두렵다.\n변화는 기회를 만든다.",
                )
                scale_raw = st.text_area(
                    "척도 앵커 (한 줄에 하나)",
                    height=120,
                    placeholder="전혀 동의하지 않는다\n동의하지 않는다\n약간 동의하지 않는다\n중립\n약간 동의한다\n동의한다\n매우 동의한다",
                )
                col1, col2, col3 = st.columns(3)
                multi = col1.checkbox("다중 선택")
                force = col2.checkbox("응답 강제")
                tag = col3.text_input("DataExportTag (선택)")
                if st.form_submit_button("질문 추가", type="primary"):
                    statements = [
                        s.strip() for s in statements_raw.splitlines() if s.strip()
                    ]
                    scale = [s.strip() for s in scale_raw.splitlines() if s.strip()]
                    if not text.strip() or len(statements) < 1 or len(scale) < 2:
                        st.error(
                            "지시문과 최소 1개 문항, 2개 척도 앵커가 필요합니다."
                        )
                    else:
                        try:
                            r = client.add_likert_matrix(
                                sid,
                                LikertMatrixInput(
                                    text=text.strip(),
                                    statements=statements,
                                    scale_points=scale,
                                    multi_select=multi,
                                    force_response=force,
                                    data_export_tag=tag or None,
                                ),
                                block_id=chosen_block_id,
                            )
                            st.success(
                                f"추가됨: QID `{r.get('QuestionID', '?')}`"
                            )
                        except QualtricsError as e:
                            st.error(f"실패: {e}")


# ─── Tab 3: 블록 & 플로우 ─────────────────────────────

with tab3:
    sid = _require_survey()
    if sid:
        st.subheader("블록 목록")
        try:
            blocks = client.list_blocks(sid)
        except QualtricsError as e:
            st.error(f"블록 조회 실패: {e}")
            blocks = []

        for b in blocks:
            bid = b["id"]
            desc = b.get("Description", "(이름 없음)")
            btype = b.get("Type", "?")
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                new_desc = c1.text_input(
                    "블록 이름", value=desc, key=f"bd-{bid}", label_visibility="collapsed"
                )
                c2.caption(f"`{bid}` · type={btype}")
                if c3.button("이름 저장", key=f"bs-{bid}"):
                    try:
                        client.update_block(sid, bid, description=new_desc)
                        st.rerun()
                    except QualtricsError as e:
                        st.error(f"실패: {e}")

        st.divider()
        st.subheader("새 블록 만들기")
        with st.form("create_block"):
            new_block_desc = st.text_input(
                "블록 이름", placeholder="예: Demographics"
            )
            if st.form_submit_button("블록 생성", type="primary"):
                if not new_block_desc.strip():
                    st.error("블록 이름은 필수입니다.")
                else:
                    try:
                        client.create_block(
                            sid, BlockInput(description=new_block_desc.strip())
                        )
                        st.success("블록 생성 완료.")
                        st.rerun()
                    except QualtricsError as e:
                        st.error(f"실패: {e}")

        st.divider()
        st.subheader("플로우")
        try:
            flow = client.get_flow(sid)
        except QualtricsError as e:
            st.error(f"플로우 조회 실패: {e}")
            flow = {}

        flow_elements = flow.get("Flow", []) if isinstance(flow, dict) else []
        if not flow_elements:
            st.info("플로우 요소가 없습니다.")
        else:
            st.write("**현재 순서**")
            for i, e in enumerate(flow_elements, 1):
                etype = e.get("Type", "?")
                eid = e.get("ID", "?")
                desc = ""
                if etype == "Block":
                    desc = next(
                        (b.get("Description", "") for b in blocks if b["id"] == eid),
                        "",
                    )
                st.write(f"{i}. `{etype}` `{eid}` {desc}")

            st.write("**블록 순서 재정렬** (현재 플로우 내 블록 ID 를 위→아래 순서로 입력)")
            block_ids_in_flow = [
                e["ID"] for e in flow_elements if e.get("Type") == "Block"
            ]
            default_order = "\n".join(block_ids_in_flow)
            with st.form("reorder_flow"):
                new_order_raw = st.text_area(
                    "블록 ID (한 줄에 하나)", value=default_order, height=120
                )
                if st.form_submit_button("순서 적용", type="primary"):
                    ids = [
                        x.strip() for x in new_order_raw.splitlines() if x.strip()
                    ]
                    try:
                        client.reorder_blocks_in_flow(sid, ids)
                        st.success("플로우 업데이트 완료.")
                        st.rerun()
                    except (QualtricsError, ValueError) as e:
                        st.error(f"실패: {e}")
