"""Report route tests."""
import pytest

from datetime import datetime, timezone
from extension import db
from Models import AnalysisJob, AnalysisType, AnalysisStatus


@pytest.fixture
def completed_job(user, empty_network, db_session):
    job = AnalysisJob(
        network_id    = empty_network.id,
        user_id       = user.id,
        analysis_type = AnalysisType.LOAD_FLOW,
        status        = AnalysisStatus.COMPLETED,
        converged     = True,
        progress_pct  = 100.0,
        started_at    = datetime.now(timezone.utc),
        completed_at  = datetime.now(timezone.utc),
        duration_sec  = 1.2,
    )
    job.results = {"summary": {"max_loading": 65.2}}
    db_session.add(job); db_session.commit()
    return job


def test_generate_report_requires_completed_job(client, auth_headers,
                                                empty_network, user,
                                                db_session):
    pending = AnalysisJob(
        network_id=empty_network.id,
        user_id=user.id,
        analysis_type=AnalysisType.LOAD_FLOW,
        status=AnalysisStatus.PENDING,
    )
    db_session.add(pending); db_session.commit()
    res = client.post("/api/reports/", headers=auth_headers,
                      json={"job_id": pending.id})
    assert res.status_code == 400


def test_generate_report_dispatch(client, auth_headers, completed_job):
    res = client.post("/api/reports/", headers=auth_headers, json={
        "job_id": completed_job.id, "format": "pdf",
    })
    assert res.status_code == 202
    body = res.get_json()["data"]["report"]
    assert body["job_id"] == completed_job.id
    assert body["format"] == "pdf"


def test_generate_report_bad_format(client, auth_headers, completed_job):
    res = client.post("/api/reports/", headers=auth_headers, json={
        "job_id": completed_job.id, "format": "docx",
    })
    assert res.status_code == 400


def test_list_reports(client, auth_headers, completed_job):
    client.post("/api/reports/", headers=auth_headers, json={
        "job_id": completed_job.id,
    })
    res = client.get("/api/reports/", headers=auth_headers)
    assert res.status_code == 200
    items = res.get_json()["data"]["reports"]
    assert len(items) >= 1


def test_get_report(client, auth_headers, completed_job):
    create = client.post("/api/reports/", headers=auth_headers, json={
        "job_id": completed_job.id,
    })
    rid = create.get_json()["data"]["report"]["id"]
    res = client.get(f"/api/reports/{rid}", headers=auth_headers)
    assert res.status_code == 200


def test_download_pending_report_returns_409(client, auth_headers,
                                              completed_job):
    create = client.post("/api/reports/", headers=auth_headers, json={
        "job_id": completed_job.id,
    })
    rid = create.get_json()["data"]["report"]["id"]
    # No file_path yet — Celery hasn't actually generated anything in tests
    res = client.get(f"/api/reports/{rid}/download", headers=auth_headers)
    assert res.status_code == 409


def test_other_user_cannot_see_report(client, auth_headers, other_headers,
                                       completed_job):
    create = client.post("/api/reports/", headers=auth_headers, json={
        "job_id": completed_job.id,
    })
    rid = create.get_json()["data"]["report"]["id"]
    res = client.get(f"/api/reports/{rid}", headers=other_headers)
    assert res.status_code == 404
