import streamlit as st

from lib.prolific import ProlificClient, ProlificError, StudyConfig
from lib.monitor import StudyMonitor
from lib.screening import SCREENING_PRESETS, build_eligibility
from shared import state


try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False


state.init()
st.title("🚀 Prolific 제어")


# ── API key ────────────────────────────────────────────────
if not state.get(state.PROLIFIC_API_KEY) and HAS_KEYRING:
    try:
        saved = keyring.get_password("vibe-prolific", "default")
        if saved:
            state.set_(state.PROLIFIC_API_KEY, saved)
    except Exception:
        pass

if not state.get(state.PROLIFIC_API_KEY):
    with st.sidebar:
        key = st.text_input("Prolific API key", type="password")
        if st.button("저장"):
            if HAS_KEYRING:
                try:
                    keyring.set_password("vibe-prolific", "default", key)
                except Exception:
                    st.warning("keyring 저장 실패 — 세션에만 저장.")
            state.set_(state.PROLIFIC_API_KEY, key)
            st.rerun()
    st.warning("좌측 사이드바에 Prolific API key 입력 필요.")
    st.stop()


client = ProlificClient(state.get(state.PROLIFIC_API_KEY))
tab1, tab2, tab3 = st.tabs(["신규 스터디", "진행 중", "응답자 승인"])


# ── Tab 1: 신규 스터디 ─────────────────────────────────
with tab1:
    title = st.text_input("스터디명", value=state.get(state.STUDY_TITLE, ""))
    completion_code = st.text_input(
        "Completion code",
        value=state.get(state.COMPLETION_CODE, ""),
    )
    expected = st.number_input(
        "예상 시간(분)",
        value=int(state.get(state.EXPECTED_MINUTES, 8)),
        min_value=1,
    )
    survey_url = st.text_input(
        "Qualtrics Survey URL",
        placeholder="https://yourorg.qualtrics.com/jfe/form/SV_xxxxx",
    )
    description = st.text_area("설명")
    places = st.number_input("모집 인원", value=30, min_value=1)
    reward_pence = st.number_input(
        "보상 (페니, £1.50 = 150)",
        value=150,
        min_value=1,
    )

    if expected > 0 and reward_pence > 0:
        hourly = (reward_pence / 100) / (expected / 60)
        if hourly < 6:
            st.error(f"시급 £{hourly:.2f}/h — Prolific 권장(£6) 미달")
        elif hourly < 8:
            st.warning(f"시급 £{hourly:.2f}/h — 권장 범위 하단")
        else:
            st.success(f"시급 £{hourly:.2f}/h ✓")

    preset = st.selectbox(
        "사전 스크리닝 프리셋",
        ["(없음)"] + list(SCREENING_PRESETS.keys()),
    )
    balanced = st.checkbox("균형 성비 (50:50)")
    submission_type = st.radio("승인 방식", ["manual", "automatic"], index=0)

    if st.button("DRAFT 생성", type="primary"):
        if not title or not survey_url or not completion_code:
            st.error("스터디명·Survey URL·Completion code 모두 필수.")
        else:
            eligibility = build_eligibility(
                preset if preset != "(없음)" else None, []
            )
            url_with_pid = survey_url.rstrip("/")
            if "PROLIFIC_PID" not in url_with_pid:
                sep = "&" if "?" in url_with_pid else "?"
                url_with_pid += f"{sep}PROLIFIC_PID={{{{%PROLIFIC_PID%}}}}"

            config = StudyConfig(
                name=title,
                description=description,
                external_study_url=url_with_pid,
                completion_code=completion_code,
                total_available_places=int(places),
                estimated_completion_time=int(expected),
                reward=int(reward_pence),
                eligibility_requirements=eligibility,
                submission_type=submission_type,
                balanced_sample=balanced,
            )
            try:
                result = client.create_study(config)
                st.success(f"DRAFT 생성: {result.get('id', '?')}")
                st.write("'진행 중' 탭에서 검토 후 publish.")
            except ProlificError as e:
                st.error(f"실패: {e}")


# ── Tab 2: 진행 중 ─────────────────────────────────────
with tab2:
    if HAS_AUTOREFRESH:
        st_autorefresh(interval=5 * 60 * 1000, key="study_refresh")

    try:
        studies = client.list_active_studies()
    except ProlificError as e:
        st.error(f"스터디 목록 조회 실패: {e}")
        studies = []

    if not studies:
        st.info("진행 중인 스터디 없음.")
    for s in studies:
        with st.container(border=True):
            st.subheader(s.get("name", "(이름 없음)"))
            mon = StudyMonitor(client, s["id"])
            try:
                snap = mon.snapshot()
            except ProlificError as e:
                st.error(f"스냅샷 실패: {e}")
                continue
            st.progress(
                min(snap.progress_pct / 100, 1.0),
                text=f"{snap.places_taken}/{snap.total_places} ({snap.progress_pct:.0f}%)",
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("완료", snap.completed)
            c2.metric("중도포기", snap.returned, f"{snap.dropout_rate*100:.0f}%")
            c3.metric("평균 시간", f"{snap.avg_time_seconds/60:.1f}분")

            for flag in mon.warning_flags(snap):
                st.warning(f"⚠ {flag}")

            colA, colB = st.columns(2)
            state_str = (s.get("status") or s.get("state") or "").upper()
            if state_str == "ACTIVE":
                if colA.button("Pause", key=f"p{s['id']}"):
                    try:
                        client.pause_study(s["id"])
                        st.rerun()
                    except ProlificError as e:
                        st.error(f"실패: {e}")
                if colB.button("Stop", key=f"s{s['id']}"):
                    try:
                        client.stop_study(s["id"])
                        st.rerun()
                    except ProlificError as e:
                        st.error(f"실패: {e}")
            elif state_str == "DRAFT":
                if st.button("Publish", key=f"pub{s['id']}", type="primary"):
                    try:
                        client.publish_study(s["id"])
                        st.rerun()
                    except ProlificError as e:
                        st.error(f"실패: {e}")


# ── Tab 3: 응답자 승인 ─────────────────────────────────
with tab3:
    try:
        studies = client.list_active_studies()
    except ProlificError as e:
        st.error(f"스터디 목록 조회 실패: {e}")
        studies = []

    if not studies:
        st.info("진행 중인 스터디 없음.")
    else:
        study_id = st.selectbox(
            "스터디 선택",
            [s["id"] for s in studies],
            format_func=lambda i: next(
                (s["name"] for s in studies if s["id"] == i), i
            ),
        )
        try:
            subs = client.list_submissions(study_id)
        except ProlificError as e:
            st.error(f"응답자 조회 실패: {e}")
            subs = []
        awaiting = [s for s in subs if s.get("status") == "AWAITING REVIEW"]
        st.write(f"**AWAITING REVIEW: {len(awaiting)}명**")

        selected: list[str] = []
        for sub in awaiting:
            time_min = (sub.get("time_taken") or 0) / 60
            flag = " ⚠ speeding" if time_min < 3 else ""
            label = (
                f"{sub.get('participant_id', sub['id'])}  "
                f"{time_min:.1f}분{flag}"
            )
            if st.checkbox(label, key=sub["id"]):
                selected.append(sub["id"])

        colA, colB = st.columns(2)
        if colA.button("선택 승인") and selected:
            for sid in selected:
                try:
                    client.approve_submission(sid)
                except ProlificError as e:
                    st.error(f"{sid} 승인 실패: {e}")
            st.success(f"{len(selected)}명 승인 처리.")
            st.rerun()

        reject_reason = st.text_input("거절 사유 (필수)")
        if colB.button("선택 거절") and selected and reject_reason:
            for sid in selected:
                try:
                    client.reject_submission(sid, reject_reason)
                except ProlificError as e:
                    st.error(f"{sid} 거절 실패: {e}")
            st.success(f"{len(selected)}명 거절 처리.")
            st.rerun()
