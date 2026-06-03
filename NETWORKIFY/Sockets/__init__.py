"""
Sockets package for PowerSys SaaS.

Flask-SocketIO event handlers for real-time analysis progress and
report-ready notifications.

Architecture
------------
  - Routes/Tasks call `emit_*` functions from Sockets.events to push
    progress without importing socketio directly everywhere.
  - Clients connect to /analysis namespace, join a user room
    "user_<user_id>", and receive their own job updates.

Usage in main.py:
    from Sockets import register_sockets
    register_sockets(socketio)
"""

from flask_socketio import SocketIO
from .analysis_socket import register_handlers as _register_analysis
from .events import (
    emit_job_queued,
    emit_job_started,
    emit_job_progress,
    emit_job_completed,
    emit_job_failed,
    emit_job_cancelled,
    emit_feasibility_completed,
    emit_report_ready,
    user_room,
)


def register_sockets(socketio : SocketIO) -> None:
    _register_analysis(socketio)


__all__ = [
    "register_sockets",
    "emit_job_queued", "emit_job_started", "emit_job_progress",
    "emit_job_completed", "emit_job_failed", "emit_job_cancelled",
    "emit_feasibility_completed", "emit_report_ready",
    "user_room",
]
