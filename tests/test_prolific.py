"""ProlificClient — httpx mock 기반 단위 테스트."""

import json

import httpx
import pytest

from lib.prolific import ProlificClient, ProlificError, StudyConfig
from lib.screening import SCREENING_PRESETS, build_eligibility


def _mock_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(
        base_url=ProlificClient.BASE_URL,
        headers={"Authorization": "Token test", "Content-Type": "application/json"},
        transport=transport,
    )


# ── create_study ────────────────────────────────────────

def test_create_study_sends_correct_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "STUDY_123", "status": "DRAFT"})

    client = ProlificClient("test", client=_mock_client(handler))
    config = StudyConfig(
        name="My Study",
        description="desc",
        external_study_url="https://example.com?PROLIFIC_PID={{%PROLIFIC_PID%}}",
        completion_code="ABC12345",
        total_available_places=30,
        estimated_completion_time=8,
        reward=150,
        eligibility_requirements=[],
    )
    result = client.create_study(config)
    assert result["id"] == "STUDY_123"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/studies/")
    assert captured["body"]["name"] == "My Study"
    assert captured["body"]["completion_code"] == "ABC12345"
    assert captured["body"]["total_available_places"] == 30
    assert captured["body"]["reward"] == 150


def test_create_study_balanced_sample_adds_quota():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "X"})

    client = ProlificClient("test", client=_mock_client(handler))
    config = StudyConfig(
        name="x", description="x",
        external_study_url="https://e.com",
        completion_code="C", total_available_places=10,
        estimated_completion_time=5, reward=50,
        eligibility_requirements=[], balanced_sample=True,
    )
    client.create_study(config)
    assert "quota_requirements" in captured["body"]
    assert len(captured["body"]["quota_requirements"]) == 2


def test_create_study_error_raises():
    def handler(request):
        return httpx.Response(400, json={"error": "bad request"})

    client = ProlificClient("test", client=_mock_client(handler))
    config = StudyConfig(
        name="x", description="x", external_study_url="https://e.com",
        completion_code="C", total_available_places=10,
        estimated_completion_time=5, reward=50,
        eligibility_requirements=[],
    )
    with pytest.raises(ProlificError):
        client.create_study(config)


# ── transitions ──────────────────────────────────────────

@pytest.mark.parametrize("method,action", [
    ("publish_study", "PUBLISH"),
    ("pause_study", "PAUSE"),
    ("stop_study", "STOP"),
])
def test_transitions(method, action):
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": action})

    client = ProlificClient("test", client=_mock_client(handler))
    getattr(client, method)("STUDY_999")
    assert "/studies/STUDY_999/transition/" in captured["url"]
    assert captured["body"] == {"action": action}


# ── get / list ──────────────────────────────────────────

def test_get_study():
    def handler(request):
        return httpx.Response(200, json={"id": "S1", "name": "test"})

    client = ProlificClient("test", client=_mock_client(handler))
    out = client.get_study("S1")
    assert out["id"] == "S1"


def test_list_active_studies_paginated_response():
    def handler(request):
        return httpx.Response(
            200,
            json={"results": [{"id": "S1"}, {"id": "S2"}], "_links": {}},
        )

    client = ProlificClient("test", client=_mock_client(handler))
    out = client.list_active_studies()
    assert len(out) == 2
    assert out[0]["id"] == "S1"


def test_list_active_studies_list_response():
    def handler(request):
        return httpx.Response(200, json=[{"id": "A"}])

    client = ProlificClient("test", client=_mock_client(handler))
    out = client.list_active_studies()
    assert out == [{"id": "A"}]


def test_list_submissions():
    def handler(request):
        return httpx.Response(
            200,
            json={"results": [
                {"id": "SUB1", "status": "AWAITING REVIEW", "time_taken": 480},
            ]},
        )

    client = ProlificClient("test", client=_mock_client(handler))
    out = client.list_submissions("S1")
    assert len(out) == 1
    assert out[0]["status"] == "AWAITING REVIEW"


# ── approve / reject ─────────────────────────────────────

def test_approve_submission():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "APPROVED"})

    client = ProlificClient("test", client=_mock_client(handler))
    client.approve_submission("SUB1")
    assert "/submissions/SUB1/transition/" in captured["url"]
    assert captured["body"]["action"] == "APPROVE"


def test_reject_submission_with_reason():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "REJECTED"})

    client = ProlificClient("test", client=_mock_client(handler))
    client.reject_submission("SUB2", "responses too fast")
    assert captured["body"]["action"] == "REJECT"
    assert captured["body"]["message"] == "responses too fast"


# ── 네트워크 오류 ───────────────────────────────────────

def test_network_error_raises():
    def handler(request):
        raise httpx.ConnectError("boom")

    client = ProlificClient("test", client=_mock_client(handler))
    with pytest.raises(ProlificError, match="네트워크"):
        client.get_study("X")


# ── screening ───────────────────────────────────────────

def test_build_eligibility_preset_only():
    out = build_eligibility("korean_speakers", [])
    assert out == SCREENING_PRESETS["korean_speakers"]


def test_build_eligibility_preset_plus_custom():
    custom = [{"category": "age", "min": 20, "max": 40}]
    out = build_eligibility("korean_workers", custom)
    assert out == SCREENING_PRESETS["korean_workers"] + custom


def test_build_eligibility_no_preset():
    custom = [{"category": "x", "values": ["y"]}]
    out = build_eligibility(None, custom)
    assert out == custom


def test_build_eligibility_unknown_preset_raises():
    with pytest.raises(ValueError, match="알 수 없"):
        build_eligibility("nonexistent", [])


# ── monitor (가벼운 검증) ────────────────────────────────

def test_monitor_snapshot_aggregates():
    from lib.monitor import StudyMonitor

    def handler(request):
        path = str(request.url.path)
        if path.endswith("/submissions/"):
            return httpx.Response(200, json={"results": [
                {"id": "S1", "status": "APPROVED", "time_taken": 480, "participant_id": "P1"},
                {"id": "S2", "status": "APPROVED", "time_taken": 600, "participant_id": "P2"},
                {"id": "S3", "status": "RETURNED", "time_taken": 0, "participant_id": "P3"},
            ]})
        return httpx.Response(200, json={
            "id": "STUDY_X",
            "name": "Test",
            "status": "ACTIVE",
            "places_taken": 3,
            "total_available_places": 10,
            "estimated_completion_time": 10,
        })

    client = ProlificClient("test", client=_mock_client(handler))
    snap = StudyMonitor(client, "STUDY_X").snapshot()
    assert snap.completed == 2
    assert snap.returned == 1
    assert snap.places_taken == 3
    assert snap.total_places == 10
    assert snap.expected_minutes == 10
    assert snap.avg_time_seconds == 540.0
    assert snap.median_time_seconds == 540.0
    assert snap.dropout_rate == pytest.approx(1 / 3)
    assert snap.progress_pct == 30.0


def test_monitor_warning_dropout():
    from lib.monitor import StudyMonitor, StudySnapshot

    snap = StudySnapshot(
        study_id="X", title="t", state="ACTIVE",
        places_taken=10, total_places=20, completed=5, in_progress=0,
        returned=3,  # 30% dropout
        avg_time_seconds=480, median_time_seconds=480,
        expected_minutes=8, speeding_suspect_ids=[],
    )
    mon = StudyMonitor(client=None, study_id="X")  # type: ignore[arg-type]
    flags = mon.warning_flags(snap)
    assert any("중도포기" in f for f in flags)


def test_monitor_warning_speeding():
    from lib.monitor import StudyMonitor, StudySnapshot

    snap = StudySnapshot(
        study_id="X", title="t", state="ACTIVE",
        places_taken=10, total_places=20, completed=10, in_progress=0,
        returned=0,
        avg_time_seconds=60,  # 1분, expected 8분 → 12.5%
        median_time_seconds=60,
        expected_minutes=8, speeding_suspect_ids=[],
    )
    mon = StudyMonitor(client=None, study_id="X")  # type: ignore[arg-type]
    flags = mon.warning_flags(snap)
    assert any("속독" in f or "주의" in f for f in flags)


def test_monitor_warning_too_slow():
    from lib.monitor import StudyMonitor, StudySnapshot

    snap = StudySnapshot(
        study_id="X", title="t", state="ACTIVE",
        places_taken=10, total_places=20, completed=10, in_progress=0,
        returned=0,
        avg_time_seconds=2000,  # 33분, expected 8분 → 4배
        median_time_seconds=2000,
        expected_minutes=8, speeding_suspect_ids=[],
    )
    mon = StudyMonitor(client=None, study_id="X")  # type: ignore[arg-type]
    flags = mon.warning_flags(snap)
    assert any("2배" in f or "지시문" in f for f in flags)


def test_monitor_no_warnings_at_baseline():
    from lib.monitor import StudyMonitor, StudySnapshot

    snap = StudySnapshot(
        study_id="X", title="t", state="ACTIVE",
        places_taken=10, total_places=20, completed=10, in_progress=0,
        returned=1,  # 10% dropout
        avg_time_seconds=480,  # 8분, exactly expected
        median_time_seconds=480,
        expected_minutes=8, speeding_suspect_ids=[],
    )
    mon = StudyMonitor(client=None, study_id="X")  # type: ignore[arg-type]
    assert mon.warning_flags(snap) == []
