"""
Report routes.

Reports are PDF or Excel deliverables generated from a completed
AnalysisJob. Generation runs in Celery (Tasks.report_tasks) and the
file is stored under app.config['REPORT_FOLDER'].

Endpoints
---------
GET    /api/reports                    List user's reports
POST   /api/reports                    Generate a new report (queues Celery)
GET    /api/reports/<id>               Get report metadata
GET    /api/reports/<id>/download      Download the file
DELETE /api/reports/<id>               Delete report (file + row)
"""
import os
from datetime import datetime, timezone

from flask import Blueprint, request, send_file, current_app
from flask_jwt_extended import jwt_required

from extension import db
from Models import AnalysisJob, AnalysisStatus, Report
from ._helpers import (
    ok, fail,
    current_user,
    get_json_body,
    require_fields,
    paginate_query,
)


report_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


# ---------------------------------------------------------------------
#  GET /
# ---------------------------------------------------------------------
@report_bp.get("/")
@jwt_required()
def list_reports():
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)

    q = Report.query
    if not user.is_admin:
        q = q.filter(Report.user_id == user.id)
    if (job_id := request.args.get("job_id")):
        try:
            q = q.filter(Report.job_id == int(job_id))
        except ValueError:
            return fail("job_id must be int", 400)
    if (fmt := request.args.get("format")):
        q = q.filter(Report.format == fmt)
    q = q.order_by(Report.created_at.desc())
    items, meta = paginate_query(q)
    return ok(
        data={"reports": [r.to_dict() for r in items]},
        pagination=meta,
    )


# ---------------------------------------------------------------------
#  POST /  (queue a generation)
# ---------------------------------------------------------------------
@report_bp.post("/")
@jwt_required()
def generate_report():
    """
    Body:
        job_id  (required) — AnalysisJob to render
        format  "pdf" | "xlsx"  default "pdf"
        title   optional
        include_diagrams  bool, default True (PDF only)
    """
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)

    data = get_json_body()
    _, err = require_fields(data, ["job_id"])
    if err:
        return err

    try:
        job_id = int(data["job_id"])
    except (TypeError, ValueError):
        return fail("job_id must be int", 400)

    job = db.session.get(AnalysisJob, job_id)
    if job is None or (job.user_id != user.id and not user.is_admin):
        return fail("Analysis job not found", 404)
    if job.status != AnalysisStatus.COMPLETED:
        return fail(
            f"Job must be completed before reporting (currently {job.status.value})",
            400,
        )

    fmt = (data.get("format") or "pdf").lower()
    if fmt not in {"pdf", "xlsx"}:
        return fail("format must be 'pdf' or 'xlsx'", 400)

    title = data.get("title") or (
        f"{job.analysis_type.value} report — job #{job.id}"
    )

    report = Report(
        job_id     = job.id,
        user_id    = user.id,
        title      = title,
        format     = fmt,
        created_at = datetime.now(timezone.utc),
    )
    db.session.add(report)
    db.session.commit()

    # TODO: from Tasks.report_tasks import generate_report_task
    # task = generate_report_task.delay(
    #     report.id,
    #     include_diagrams=bool(data.get("include_diagrams", True)),
    # )
    return ok(
        data={"report": report.to_dict()},
        message="Report generation queued",
        status=202,
    )


# ---------------------------------------------------------------------
#  GET /<id>
# ---------------------------------------------------------------------
@report_bp.get("/<int:report_id>")
@jwt_required()
def get_report(report_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    report = db.session.get(Report, report_id)
    if report is None or (report.user_id != user.id and not user.is_admin):
        return fail("Report not found", 404)
    return ok(data={"report": report.to_dict()})


# ---------------------------------------------------------------------
#  GET /<id>/download
# ---------------------------------------------------------------------
@report_bp.get("/<int:report_id>/download")
@jwt_required()
def download_report(report_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    report = db.session.get(Report, report_id)
    if report is None or (report.user_id != user.id and not user.is_admin):
        return fail("Report not found", 404)
    if not report.file_path:
        return fail("Report file is not ready yet", 409)

    # Resolve path relative to REPORT_FOLDER when stored as a relative key
    base = current_app.config.get("REPORT_FOLDER", "reports")
    full_path = report.file_path
    if not os.path.isabs(full_path):
        full_path = os.path.join(base, full_path)
    if not os.path.exists(full_path):
        return fail("Report file is missing from disk", 410)

    report.download_count = (report.download_count or 0) + 1
    db.session.commit()

    mimetypes = {
        "pdf":  "application/pdf",
        "xlsx": ("application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"),
    }
    safe_title = "".join(
        c if c.isalnum() or c in " ._-" else "_" for c in report.title
    ).strip() or f"report_{report.id}"
    return send_file(
        full_path,
        mimetype=mimetypes.get(report.format, "application/octet-stream"),
        as_attachment=True,
        download_name=f"{safe_title}.{report.format}",
    )


# ---------------------------------------------------------------------
#  DELETE /<id>
# ---------------------------------------------------------------------
@report_bp.delete("/<int:report_id>")
@jwt_required()
def delete_report(report_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    report = db.session.get(Report, report_id)
    if report is None or (report.user_id != user.id and not user.is_admin):
        return fail("Report not found", 404)

    # Remove the file from disk if present
    if report.file_path:
        base = current_app.config.get("REPORT_FOLDER", "reports")
        full_path = report.file_path
        if not os.path.isabs(full_path):
            full_path = os.path.join(base, full_path)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
        except OSError:
            pass  # best-effort
    db.session.delete(report)
    db.session.commit()
    return ok(message="Report deleted")
