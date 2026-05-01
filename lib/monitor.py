"""Study 진행 상황 모니터링 + 경고 플래그."""

from __future__ import annotations

import statistics

from pydantic import BaseModel

from .prolific import ProlificClient


class StudySnapshot(BaseModel):
    study_id: str
    title: str
    state: str
    places_taken: int
    total_places: int
    completed: int
    in_progress: int
    returned: int
    avg_time_seconds: float
    median_time_seconds: float
    expected_minutes: int
    speeding_suspect_ids: list[str]

    @property
    def progress_pct(self) -> float:
        if self.total_places == 0:
            return 0.0
        return self.places_taken / self.total_places * 100

    @property
    def dropout_rate(self) -> float:
        if self.places_taken == 0:
            return 0.0
        return self.returned / self.places_taken


class StudyMonitor:
    def __init__(self, client: ProlificClient, study_id: str):
        self.client = client
        self.study_id = study_id

    def snapshot(self) -> StudySnapshot:
        study = self.client.get_study(self.study_id)
        subs = self.client.list_submissions(self.study_id)

        completed = sum(1 for s in subs if s.get("status") in ("APPROVED", "AWAITING REVIEW"))
        in_progress = sum(1 for s in subs if s.get("status") == "ACTIVE")
        returned = sum(1 for s in subs if s.get("status") in ("RETURNED", "TIMED-OUT"))

        times = [
            float(s["time_taken"]) for s in subs
            if isinstance(s.get("time_taken"), (int, float)) and s["time_taken"] > 0
        ]
        avg_t = sum(times) / len(times) if times else 0.0
        med_t = statistics.median(times) if times else 0.0
        expected_min = int(study.get("estimated_completion_time", 0) or 0)

        # speeding 의심: 예상의 30% 미만 시간
        speeding_threshold = expected_min * 60 * 0.30 if expected_min > 0 else 180.0
        speeding = [
            s.get("participant_id", s.get("id", "?"))
            for s in subs
            if isinstance(s.get("time_taken"), (int, float))
            and 0 < s["time_taken"] < speeding_threshold
        ]

        return StudySnapshot(
            study_id=self.study_id,
            title=study.get("name", ""),
            state=study.get("status", study.get("state", "UNKNOWN")),
            places_taken=int(study.get("places_taken", 0) or 0),
            total_places=int(study.get("total_available_places", 0) or 0),
            completed=completed,
            in_progress=in_progress,
            returned=returned,
            avg_time_seconds=avg_t,
            median_time_seconds=med_t,
            expected_minutes=expected_min,
            speeding_suspect_ids=speeding,
        )

    def warning_flags(self, snap: StudySnapshot) -> list[str]:
        flags: list[str] = []
        if snap.dropout_rate > 0.20:
            flags.append(
                f"중도포기율이 {snap.dropout_rate*100:.0f}% — 20% 초과. "
                "설문 길이·난이도 점검 필요."
            )
        if snap.expected_minutes > 0 and snap.avg_time_seconds > 0:
            expected_sec = snap.expected_minutes * 60
            if snap.avg_time_seconds < expected_sec * 0.30:
                flags.append(
                    f"평균 응답 시간 {snap.avg_time_seconds/60:.1f}분 — "
                    f"예상({snap.expected_minutes}분)의 30% 미만. "
                    "주의 검사·속독 응답 가능성."
                )
            elif snap.avg_time_seconds > expected_sec * 2.00:
                flags.append(
                    f"평균 응답 시간 {snap.avg_time_seconds/60:.1f}분 — "
                    f"예상({snap.expected_minutes}분)의 2배 초과. "
                    "지시문 명확성·UI 점검 필요."
                )
        return flags
