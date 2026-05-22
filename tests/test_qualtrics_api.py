"""QualtricsClient — httpx mock 기반 단위 테스트."""

from __future__ import annotations

import json

import httpx
import pytest

from lib.qualtrics_api import (
    BlockInput,
    LikertMatrixInput,
    MultipleChoiceInput,
    QualtricsClient,
    QualtricsError,
    SurveyConfig,
    TextEntryInput,
)


DC = "syd1"
BASE = f"https://{DC}.qualtrics.com/API/v3"


def _mock_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(
        base_url=BASE,
        headers={"X-API-TOKEN": "test", "Content-Type": "application/json"},
        transport=transport,
    )


def _make(handler) -> QualtricsClient:
    return QualtricsClient("test-token", DC, client=_mock_client(handler))


# ─── 인증 ───────────────────────────────────────────────────────

def test_constructor_requires_token_and_dc():
    with pytest.raises(ValueError):
        QualtricsClient("", DC)
    with pytest.raises(ValueError):
        QualtricsClient("t", "")


def test_request_unwraps_result_envelope():
    def handler(request):
        return httpx.Response(
            200,
            json={"result": {"foo": "bar"}, "meta": {"httpStatus": "200 - OK"}},
        )

    client = _make(handler)
    assert client.get_survey("SV_123") == {"foo": "bar"}


def test_request_raises_on_400():
    def handler(request):
        return httpx.Response(400, text="bad input")

    client = _make(handler)
    with pytest.raises(QualtricsError, match="400"):
        client.get_survey("SV_123")


# ─── 서베이 CRUD ────────────────────────────────────────────────

def test_create_survey_sends_correct_body():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"SurveyID": "SV_abc"}})

    client = _make(handler)
    result = client.create_survey(
        SurveyConfig(name="Test Survey", language="KO")
    )
    assert result == {"SurveyID": "SV_abc"}
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/survey-definitions")
    assert captured["body"] == {
        "SurveyName": "Test Survey",
        "Language": "KO",
        "ProjectCategory": "CORE",
    }


def test_list_surveys_returns_elements():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "result": {
                    "elements": [
                        {"id": "SV_1", "name": "A", "isActive": True},
                        {"id": "SV_2", "name": "B", "isActive": False},
                    ]
                }
            },
        )

    client = _make(handler)
    items = client.list_surveys()
    assert len(items) == 2
    assert items[0]["id"] == "SV_1"


def test_list_surveys_empty_when_no_elements():
    def handler(request):
        return httpx.Response(200, json={"result": {}})

    client = _make(handler)
    assert client.list_surveys() == []


def test_activate_survey_puts_is_active_true():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {}})

    client = _make(handler)
    client.activate_survey("SV_abc")
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/surveys/SV_abc")
    assert captured["body"] == {"isActive": True}


def test_deactivate_survey_puts_is_active_false():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {}})

    client = _make(handler)
    client.deactivate_survey("SV_abc")
    assert captured["body"] == {"isActive": False}


def test_update_survey_metadata_requires_field():
    def handler(request):
        return httpx.Response(200, json={"result": {}})

    client = _make(handler)
    with pytest.raises(ValueError):
        client.update_survey_metadata("SV_abc")


def test_delete_survey_deletes_definition():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"result": {}})

    client = _make(handler)
    client.delete_survey("SV_abc")
    assert captured["method"] == "DELETE"
    assert captured["url"].endswith("/survey-definitions/SV_abc")


# ─── 블록 ───────────────────────────────────────────────────────

def test_list_blocks_flattens_dict():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "result": {
                    "Blocks": {
                        "BL_a": {"Description": "Intro", "Type": "Standard"},
                        "BL_b": {"Description": "Outro", "Type": "Standard"},
                    }
                }
            },
        )

    client = _make(handler)
    blocks = client.list_blocks("SV_x")
    ids = sorted(b["id"] for b in blocks)
    assert ids == ["BL_a", "BL_b"]


def test_create_block_posts_to_blocks_endpoint():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"BlockID": "BL_new"}})

    client = _make(handler)
    client.create_block("SV_x", BlockInput(description="Demographics"))
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/survey-definitions/SV_x/blocks")
    assert captured["body"] == {"Type": "Standard", "Description": "Demographics"}


# ─── 질문 helper ────────────────────────────────────────────────

def test_add_multiple_choice_single_answer_payload():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"QuestionID": "QID1"}})

    client = _make(handler)
    client.add_multiple_choice(
        "SV_x",
        MultipleChoiceInput(
            text="What is your favorite color?",
            choices=["Red", "Blue", "Green"],
        ),
    )
    body = captured["body"]
    assert body["QuestionType"] == "MC"
    assert body["Selector"] == "SAVR"
    assert body["SubSelector"] == "TX"
    assert body["ChoiceOrder"] == [1, 2, 3]
    assert body["Choices"]["1"]["Display"] == "Red"
    assert body["Validation"]["Settings"]["ForceResponse"] == "OFF"


def test_add_multiple_choice_multi_select_uses_mavr():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"QuestionID": "Q1"}})

    client = _make(handler)
    client.add_multiple_choice(
        "SV_x",
        MultipleChoiceInput(
            text="Select all that apply",
            choices=["A", "B"],
            multi_select=True,
            force_response=True,
            data_export_tag="prefs",
        ),
    )
    body = captured["body"]
    assert body["Selector"] == "MAVR"
    assert body["DataExportTag"] == "prefs"
    assert body["Validation"]["Settings"]["ForceResponse"] == "ON"


def test_add_multiple_choice_with_block_id_passes_query_param():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"result": {"QuestionID": "Q1"}})

    client = _make(handler)
    client.add_multiple_choice(
        "SV_x",
        MultipleChoiceInput(text="?", choices=["a", "b"]),
        block_id="BL_target",
    )
    assert "blockId=BL_target" in captured["url"]


def test_add_text_entry_payload():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"QuestionID": "Q1"}})

    client = _make(handler)
    client.add_text_entry(
        "SV_x", TextEntryInput(text="Your thoughts?", selector="ML")
    )
    body = captured["body"]
    assert body["QuestionType"] == "TE"
    assert body["Selector"] == "ML"


def test_add_likert_matrix_payload_has_answers_and_choices():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"QuestionID": "Q1"}})

    client = _make(handler)
    client.add_likert_matrix(
        "SV_x",
        LikertMatrixInput(
            text="Rate each",
            statements=["S1", "S2", "S3"],
            scale_points=["Disagree", "Neutral", "Agree"],
        ),
    )
    body = captured["body"]
    assert body["QuestionType"] == "Matrix"
    assert body["Selector"] == "Likert"
    assert body["SubSelector"] == "SingleAnswer"
    assert body["ChoiceOrder"] == [1, 2, 3]
    assert body["AnswerOrder"] == [1, 2, 3]
    assert body["Choices"]["2"]["Display"] == "S2"
    assert body["Answers"]["3"]["Display"] == "Agree"


def test_add_likert_multi_select_uses_multiple_answer():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {"QuestionID": "Q1"}})

    client = _make(handler)
    client.add_likert_matrix(
        "SV_x",
        LikertMatrixInput(
            text="Rate",
            statements=["S1"],
            scale_points=["1", "2"],
            multi_select=True,
        ),
    )
    assert captured["body"]["SubSelector"] == "MultipleAnswer"


def test_choices_dict_rejects_empty():
    with pytest.raises(ValueError):
        QualtricsClient._choices_dict([])


# ─── 플로우 ─────────────────────────────────────────────────────

def test_reorder_blocks_keeps_non_block_elements():
    """Block 이 아닌 EndOfSurvey 등은 보존되고, Block 요소만 재정렬되어야 함."""
    flow_state = {
        "Flow": [
            {"Type": "Block", "ID": "BL_a"},
            {"Type": "Block", "ID": "BL_b"},
            {"Type": "EndOfSurvey", "ID": "EOS"},
        ]
    }
    captured_put = {}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"result": flow_state})
        captured_put["body"] = json.loads(request.content)
        return httpx.Response(200, json={"result": {}})

    client = _make(handler)
    client.reorder_blocks_in_flow("SV_x", ["BL_b", "BL_a"])

    new_flow = captured_put["body"]["Flow"]
    assert [e["ID"] for e in new_flow] == ["BL_b", "BL_a", "EOS"]


def test_reorder_blocks_rejects_unknown_id():
    flow_state = {"Flow": [{"Type": "Block", "ID": "BL_a"}]}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"result": flow_state})
        return httpx.Response(200, json={"result": {}})

    client = _make(handler)
    with pytest.raises(ValueError, match="BL_zz"):
        client.reorder_blocks_in_flow("SV_x", ["BL_a", "BL_zz"])
