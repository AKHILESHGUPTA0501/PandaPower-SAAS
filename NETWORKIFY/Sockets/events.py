"""
Emit helpers — callers in Routes and Tasks use these instead of
talking to socketio directly.

Every payload is JSON-serialisable and routed to a per-user room
("user_<id>") under the /analysis namespace.
"""
from typing import Any
from extension import socketio
from Utils.constants import (
    SIO_NAMESPACE,
    SIO_EVENT_JOB_QUEUED,
    SIO_EVENT_JOB_STARTED,
    SIO_EVENT_JOB_PROGRESS,
    SIO_EVENT_JOB_COMPLETED,
    SIO_EVENT_JOB_FAILED,
    SIO_EVENT_JOB_CANCELLED,
    SIO_EVENT_FEASIBILITY_DONE,
    SIO_EVENT_REPORT_READY,
)
from Utils.logger import get_logger

_log = get_logger(__name__)

def user_room(user_id : int) -> str:
    return f'user_{user_id}'

def _emit(event : str, user_id : int, payload : dict[str, Any]) -> None:
    try:
        socketio.emit(
            event,
            payload,
            namespace= SIO_NAMESPACE,
            room = user_room(user_id)
        )
    except Exception as e:
        _log.warning('socket emit failed (%s): %s', event, e)
    
def emit_job_queued(user_id : int, job_id : int, analysis_type : str) -> None:
    _emit(SIO_EVENT_JOB_QUEUED, user_id, {
        "job_id":         job_id,
        "analysis_type":  analysis_type,
        "status":         "pending",
    })

def emit_job_started(user_id : int, job_id : int, analysis_type :str) -> None:
    _emit(SIO_EVENT_JOB_STARTED, user_id, {
        "job_id":         job_id,
        "analysis_type":  analysis_type,
        "status":         "running",
    })

def emit_job_progress(user_id: int, job_id: int, percent: float,
                    message: str | None = None) -> None:
    _emit(SIO_EVENT_JOB_PROGRESS, user_id, {
        "job_id":   job_id,
        "progress": round(float(percent), 2),
        "message":  message,
    })


def emit_job_completed(user_id: int, job_id: int, analysis_type: str,
                        summary: dict | None = None) -> None:
    _emit(SIO_EVENT_JOB_COMPLETED, user_id, {
        "job_id":         job_id,
        "analysis_type":  analysis_type,
        "status":         "completed",
        "summary":        summary or {},
    })


def emit_job_failed(user_id: int, job_id: int, analysis_type: str,
                    error: str) -> None:
    _emit(SIO_EVENT_JOB_FAILED, user_id, {
        "job_id":         job_id,
        "analysis_type":  analysis_type,
        "status":         "failed",
        "error":          error,
    })


def emit_job_cancelled(user_id: int, job_id: int) -> None:
    _emit(SIO_EVENT_JOB_CANCELLED, user_id, {
        "job_id":  job_id,
        "status":  "cancelled",
    })


# =====================================================================
#  Feasibility
# =====================================================================
def emit_feasibility_completed(user_id: int, study_id: int,
                                verdict: str, summary: dict | None = None) -> None:
    _emit(SIO_EVENT_FEASIBILITY_DONE, user_id, {
        "study_id": study_id,
        "verdict":  verdict,
        "summary":  summary or {},
    })


# =====================================================================
#  Report
# =====================================================================
def emit_report_ready(user_id: int, report_id: int, fmt: str,
                    job_id: int | None = None) -> None:
    _emit(SIO_EVENT_REPORT_READY, user_id, {
        "report_id": report_id,
        "job_id":    job_id,
        "format":    fmt,
    })