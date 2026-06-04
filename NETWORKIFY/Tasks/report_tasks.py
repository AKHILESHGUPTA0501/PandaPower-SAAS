"""
Report generation Celery tasks.
"""
import os
from datetime import datetime, timedelta, timezone

from flask import current_app
from celery.exceptions import SoftTimeLimitExceeded

from extension import celery, db
from Models import Report, AnalysisJob, AnalysisStatus
from Services import ReportService
from Sockets.events import emit_report_ready, emit_job_failed
from Utils.logger import get_logger


_log = get_logger(__name__)


@celery.task(
    name="report.generate",
    bind=True,
    soft_time_limit=600,
    time_limit=900,
    max_retries=1,
    default_retry_delay=15,
)
def generate_report_task(self, report_id :int, include_diagrams : bool = True):
    report = db.session.get(Report, report_id)
    if report is None:
        _log.error('report %s not found', report_id)
        return {'ok': False, 'reason': 'report not found'}
    job = db.session.get(AnalysisJob, report.job_id) if report.job_id else None
    if job is None:
        _log.error('report %s references missing job', report_id)
        return {'ok': False, 'reason': 'Job not found'}
    if job.status != AnalysisStatus.COMPLETED:
        return {'ok': False, 'reason': f'job_status_{job.status_value}'}
    try:
        ReportService.genearte(report.id, include_diagrams= include_diagrams)
        db.session.refresh(report)
        emit_report_ready(
            report.user_id, report.id, report.format, job_id=report.job_id,
        )
        return {
            "ok":             True,
            "report_id":      report.id,
            "file_path":      report.file_path,
            "file_size_bytes":report.file_size_bytes,
        }
    except SoftTimeLimitExceeded:
        _log.error('report %s timed out', report_id)
        emit_job_failed(report.user_id, report.id, 'report', 'Report generation timed out')
        return {'ok': False, 'reason': 'time_limit'}
    except Exception as e:
        _log.exception('report %s generation failed', report_id)
        emit_job_failed(report.user_id, report.id, 'report', str(e))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'ok': False, 'reason': 'exeception', 'error': str(e)}
    

@celery.task(name = 'report.cleanup_old', bind = True, max_retries = 0)
def cleanup_old_reports_task(self, days: int = 30):
    cutoff = datetime.now(timezone.utc) - timedelta(days = days)
    base = current_app.config.get('REPORT_FOLDER', 'reports')
    removed= 0
    bytes_freed = 0
    candidates = (Report.query
                  .filter(Report.created_at < cutoff)
                  .filter(Report.file_path.isnot(None))
                  .all())
    for r in candidates:
        path = r.file_path
        if path and not os.path.isabs(path):
            path = os.path.join(base, path)
        if path and os.path.exists(path):
            try:
                bytes_freed += os.path.getsize(path)
                os.remove(path)
                removed += 1
            except OSError as e:
                _log.warning('Could not remove %s: %s', path, e)
        r.file_path = None
        r.file_size_bytes = None
    db.session.commit()
    return {'removed_files': removed, 'bytes_freed': bytes_freed, 'days': days}
