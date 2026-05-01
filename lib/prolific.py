"""Prolific API 클라이언트."""

from __future__ import annotations

from typing import Literal

import httpx
from pydantic import BaseModel


class StudyConfig(BaseModel):
    name: str
    description: str
    external_study_url: str
    completion_code: str
    total_available_places: int
    estimated_completion_time: int
    reward: int
    eligibility_requirements: list[dict]
    submission_type: Literal["manual", "automatic"] = "manual"
    balanced_sample: bool = False


class ProlificError(Exception):
    """Prolific API 호출 실패."""


class ProlificClient:
    BASE_URL = "https://api.prolific.com/api/v1"

    def __init__(self, api_key: str, *, client: httpx.Client | None = None):
        self._api_key = api_key
        self._client = client or httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    # ─── 내부 ─────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            r = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise ProlificError(f"네트워크 오류: {e}") from e
        if r.status_code >= 400:
            raise ProlificError(
                f"Prolific API {r.status_code}: {r.text[:300]}"
            )
        if not r.content:
            return {}
        try:
            return r.json()
        except ValueError:
            return {"raw": r.text}

    # ─── Study CRUD ───────────────────────────────────────

    def create_study(self, config: StudyConfig) -> dict:
        body = {
            "name": config.name,
            "internal_name": config.name,
            "description": config.description,
            "external_study_url": config.external_study_url,
            "prolific_id_option": "url_parameters",
            "completion_code": config.completion_code,
            "completion_option": "code",
            "total_available_places": config.total_available_places,
            "estimated_completion_time": config.estimated_completion_time,
            "reward": config.reward,
            "eligibility_requirements": config.eligibility_requirements,
            "device_compatibility": ["desktop"],
            "peripheral_requirements": [],
            "submission_type": config.submission_type,
            "naivety_distribution_rate": None,
            "project": None,
        }
        if config.balanced_sample:
            body["quota_requirements"] = [
                {
                    "filters": [
                        {"filter_id": "sex", "selected_values": ["1"]}
                    ],
                    "value": 50,
                },
                {
                    "filters": [
                        {"filter_id": "sex", "selected_values": ["2"]}
                    ],
                    "value": 50,
                },
            ]
        return self._request("POST", "/studies/", json=body)

    def get_study(self, study_id: str) -> dict:
        return self._request("GET", f"/studies/{study_id}/")

    def list_active_studies(self) -> list[dict]:
        data = self._request("GET", "/studies/", params={"state": "ACTIVE"})
        if isinstance(data, dict):
            return data.get("results", []) or []
        return data if isinstance(data, list) else []

    # ─── Transitions ─────────────────────────────────────

    def _transition(self, study_id: str, action: str) -> dict:
        return self._request(
            "POST",
            f"/studies/{study_id}/transition/",
            json={"action": action},
        )

    def publish_study(self, study_id: str) -> dict:
        return self._transition(study_id, "PUBLISH")

    def pause_study(self, study_id: str) -> dict:
        return self._transition(study_id, "PAUSE")

    def stop_study(self, study_id: str) -> dict:
        return self._transition(study_id, "STOP")

    # ─── Submissions ─────────────────────────────────────

    def list_submissions(self, study_id: str) -> list[dict]:
        data = self._request("GET", f"/studies/{study_id}/submissions/")
        if isinstance(data, dict):
            return data.get("results", []) or []
        return data if isinstance(data, list) else []

    def approve_submission(self, sub_id: str) -> dict:
        return self._request(
            "POST",
            f"/submissions/{sub_id}/transition/",
            json={"action": "APPROVE"},
        )

    def reject_submission(self, sub_id: str, reason: str) -> dict:
        return self._request(
            "POST",
            f"/submissions/{sub_id}/transition/",
            json={
                "action": "REJECT",
                "rejection_category": "OTHER",
                "message": reason,
            },
        )

    def close(self) -> None:
        self._client.close()
