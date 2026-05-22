"""Qualtrics REST API v3 클라이언트.

yrvelez/qualtrics-mcp-server 가 노출하는 MCP tool 중 학생 실습에 필요한
범위(서베이 CRUD + 객관식·텍스트·Likert 매트릭스 질문 추가 + 블록·플로우
관리)만 Python 으로 옮긴 얇은 래퍼. lib 내 다른 모듈은 import 하지 않음.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel


# ─── 데이터 모델 ─────────────────────────────────────────────

class SurveyConfig(BaseModel):
    name: str
    language: str = "EN"
    project_category: str = "CORE"


class MultipleChoiceInput(BaseModel):
    text: str
    choices: list[str]
    multi_select: bool = False
    data_export_tag: str | None = None
    force_response: bool = False


class TextEntryInput(BaseModel):
    text: str
    selector: Literal["SL", "ML", "ESTB"] = "SL"
    data_export_tag: str | None = None
    force_response: bool = False


class LikertMatrixInput(BaseModel):
    text: str
    statements: list[str]
    scale_points: list[str]
    multi_select: bool = False
    data_export_tag: str | None = None
    force_response: bool = False


class BlockInput(BaseModel):
    description: str
    type: Literal["Standard", "Default", "Trash"] = "Standard"


class QualtricsError(Exception):
    """Qualtrics API 호출 실패."""


# ─── 클라이언트 ──────────────────────────────────────────────

class QualtricsClient:
    """Qualtrics REST API v3 래퍼.

    엔드포인트 매핑은 https://api.qualtrics.com/ 공식 문서 기준.
    """

    def __init__(
        self,
        api_token: str,
        data_center: str,
        *,
        client: httpx.Client | None = None,
    ):
        if not api_token:
            raise ValueError("api_token 비어 있음")
        if not data_center:
            raise ValueError("data_center 비어 있음")
        self._api_token = api_token
        self._data_center = data_center
        self._base_url = f"https://{data_center}.qualtrics.com/API/v3"
        self._client = client or httpx.Client(
            base_url=self._base_url,
            headers={
                "X-API-TOKEN": api_token,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    # ─── 내부 ────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            r = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise QualtricsError(f"네트워크 오류: {e}") from e
        if r.status_code >= 400:
            raise QualtricsError(
                f"Qualtrics API {r.status_code} {method} {path}: {r.text[:400]}"
            )
        if not r.content:
            return {}
        try:
            payload = r.json()
        except ValueError:
            return {"raw": r.text}
        if isinstance(payload, dict) and "result" in payload:
            return payload["result"] or {}
        return payload

    # ─── 서베이 CRUD ─────────────────────────────────────

    def create_survey(self, config: SurveyConfig) -> dict:
        body = {
            "SurveyName": config.name,
            "Language": config.language,
            "ProjectCategory": config.project_category,
        }
        return self._request("POST", "/survey-definitions", json=body)

    def list_surveys(self) -> list[dict]:
        data = self._request("GET", "/surveys")
        return data.get("elements", []) if isinstance(data, dict) else []

    def get_survey(self, survey_id: str) -> dict:
        return self._request("GET", f"/survey-definitions/{survey_id}")

    def update_survey_metadata(
        self,
        survey_id: str,
        *,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> dict:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if is_active is not None:
            body["isActive"] = is_active
        if not body:
            raise ValueError("name·is_active 중 최소 하나 필요")
        return self._request("PUT", f"/surveys/{survey_id}", json=body)

    def activate_survey(self, survey_id: str) -> dict:
        return self.update_survey_metadata(survey_id, is_active=True)

    def deactivate_survey(self, survey_id: str) -> dict:
        return self.update_survey_metadata(survey_id, is_active=False)

    def delete_survey(self, survey_id: str) -> dict:
        return self._request("DELETE", f"/survey-definitions/{survey_id}")

    # ─── 블록 ───────────────────────────────────────────

    def list_blocks(self, survey_id: str) -> list[dict]:
        """survey-definition 의 Blocks 딕셔너리를 리스트로 반환."""
        survey = self.get_survey(survey_id)
        blocks = survey.get("Blocks", {}) or {}
        out: list[dict] = []
        for block_id, b in blocks.items():
            out.append({"id": block_id, **b})
        return out

    def create_block(self, survey_id: str, block: BlockInput) -> dict:
        body = {"Type": block.type, "Description": block.description}
        return self._request(
            "POST", f"/survey-definitions/{survey_id}/blocks", json=body
        )

    def update_block(
        self, survey_id: str, block_id: str, *, description: str
    ) -> dict:
        body = {"Description": description, "Type": "Standard"}
        return self._request(
            "PUT",
            f"/survey-definitions/{survey_id}/blocks/{block_id}",
            json=body,
        )

    def delete_block(self, survey_id: str, block_id: str) -> dict:
        return self._request(
            "DELETE", f"/survey-definitions/{survey_id}/blocks/{block_id}"
        )

    # ─── 질문 (helper) ─────────────────────────────────

    def _post_question(
        self, survey_id: str, payload: dict, block_id: str | None
    ) -> dict:
        params = {"blockId": block_id} if block_id else None
        return self._request(
            "POST",
            f"/survey-definitions/{survey_id}/questions",
            params=params,
            json=payload,
        )

    @staticmethod
    def _choices_dict(items: list[str]) -> tuple[dict, list[int]]:
        if not items:
            raise ValueError("선택지/문항이 최소 1개 필요")
        choices = {str(i + 1): {"Display": text} for i, text in enumerate(items)}
        order = list(range(1, len(items) + 1))
        return choices, order

    @staticmethod
    def _validation(force: bool) -> dict:
        return {
            "Settings": {
                "ForceResponse": "ON" if force else "OFF",
                "Type": "None",
            }
        }

    def add_multiple_choice(
        self,
        survey_id: str,
        q: MultipleChoiceInput,
        *,
        block_id: str | None = None,
    ) -> dict:
        choices, order = self._choices_dict(q.choices)
        payload = {
            "QuestionText": q.text,
            "QuestionType": "MC",
            "Selector": "MAVR" if q.multi_select else "SAVR",
            "SubSelector": "TX",
            "Configuration": {"QuestionDescriptionOption": "UseText"},
            "QuestionDescription": q.text[:100],
            "Choices": choices,
            "ChoiceOrder": order,
            "Validation": self._validation(q.force_response),
            "Language": [],
            "DataExportTag": q.data_export_tag or "",
        }
        return self._post_question(survey_id, payload, block_id)

    def add_text_entry(
        self,
        survey_id: str,
        q: TextEntryInput,
        *,
        block_id: str | None = None,
    ) -> dict:
        payload = {
            "QuestionText": q.text,
            "QuestionType": "TE",
            "Selector": q.selector,
            "Configuration": {"QuestionDescriptionOption": "UseText"},
            "QuestionDescription": q.text[:100],
            "Validation": self._validation(q.force_response),
            "Language": [],
            "DataExportTag": q.data_export_tag or "",
        }
        return self._post_question(survey_id, payload, block_id)

    def add_likert_matrix(
        self,
        survey_id: str,
        q: LikertMatrixInput,
        *,
        block_id: str | None = None,
    ) -> dict:
        statements, stmt_order = self._choices_dict(q.statements)
        answers, ans_order = self._choices_dict(q.scale_points)
        payload = {
            "QuestionText": q.text,
            "QuestionType": "Matrix",
            "Selector": "Likert",
            "SubSelector": "MultipleAnswer" if q.multi_select else "SingleAnswer",
            "Configuration": {
                "QuestionDescriptionOption": "UseText",
                "TextPosition": "inline",
                "ChoiceColumnWidth": 25,
                "RepeatHeaders": "none",
                "WhiteSpace": "ON",
            },
            "QuestionDescription": q.text[:100],
            "Choices": statements,
            "ChoiceOrder": stmt_order,
            "Answers": answers,
            "AnswerOrder": ans_order,
            "ChoiceDataExportTags": False,
            "Validation": self._validation(q.force_response),
            "Language": [],
            "DataExportTag": q.data_export_tag or "",
        }
        return self._post_question(survey_id, payload, block_id)

    # ─── 플로우 ─────────────────────────────────────────

    def get_flow(self, survey_id: str) -> dict:
        return self._request("GET", f"/survey-definitions/{survey_id}/flow")

    def update_flow(self, survey_id: str, flow: dict) -> dict:
        return self._request(
            "PUT",
            f"/survey-definitions/{survey_id}/flow",
            json=flow,
        )

    def reorder_blocks_in_flow(
        self, survey_id: str, block_ids_in_order: list[str]
    ) -> dict:
        """플로우 최상단 Block 엔트리만 주어진 순서로 정렬, 나머지는 보존."""
        flow = self.get_flow(survey_id)
        elements = flow.get("Flow", [])
        block_elems = {
            e.get("ID"): e for e in elements if e.get("Type") == "Block"
        }
        missing = [b for b in block_ids_in_order if b not in block_elems]
        if missing:
            raise ValueError(f"플로우에 없는 블록 ID: {missing}")
        non_block = [e for e in elements if e.get("Type") != "Block"]
        reordered = [block_elems[b] for b in block_ids_in_order]
        flow["Flow"] = reordered + non_block
        return self.update_flow(survey_id, flow)

    def close(self) -> None:
        self._client.close()
