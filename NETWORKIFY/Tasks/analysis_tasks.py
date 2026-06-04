"""
Analysis Celery tasks.

Each task:
  1. Loads the AnalysisJob row.
  2. Emits `job_started` over Socket.IO.
  3. Delegates to the matching Service class.
  4. Emits `job_completed` or `job_failed`.

All Service methods already wrap their own try/except and mark
the job COMPLETED/FAILED, so the Celery handler is thin.
"""
from datetime import datetime, timezone
from celery.exceptions import SoftTimeLimitExceeded

from extension import celery, db
from Models import (
    AnalysisJob, AnalysisStatus, AnalysisType,
    FeasibilityStudy
)

from Services import (
    LoadFlowService,
    ShortCircuitService,
    ContingencyService,
    OPFService,
    TimeSeriesService,
    FeasibilityService,
)

from Sockets.events import (
    emit_job_started,
    emit_job_progress,
    emit_job_completed,
    emit_job_failed,
    emit_job_cancelled,
    emit_feasibility_completed,
)
from Utils.logger import get_logger

_log  = get_logger(__name__)

def _run_analysis(job_id : int, service_cls, analysis_label : str) -> dict:
    job = db.session.get(AnalysisJob, job_id)
    if job is None:
        _log.error('%s: Job %s not found', analysis_label, job_id)
        return {'ok' : False, 'reason': 'Job not found'}
    if job.status == AnalysisStatus.CANCELLED:
        emit_job_cancelled(job.user_id, job.id)
        return {'ok': False, 'reason': 'Cancelled'}
    emit_job_started(job.user_id, job.id, job.analysis_type.value)
    emit_job_progress(job.user_id, job.id, 1.0, 'started')
    try:
        summary = service_cls.run(job.id)
        db.session.refresh(job)
        emit_job_progress(job.user_id, job_id, 100.0,'done')
        emit_job_completed(
            job.user_id, job.id, job.analysis_type.value,
            summary= summary
        )
        return {'ok' : True, 'job_id': job.id, 'summary': summary}
    except SoftTimeLimitExceeded:
        job.status = AnalysisStatus.FAILED
        job.error_message = 'Analysis exceeded time limit'
        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        emit_job_failed(job.user_id, job.id, job.analysis_type.value,
                        'Analysis exceeded time limit')
        return {'ok': False, 'reason': 'time_limit'}
    except Exception as e:
        _log.exception('%s job %s failed', analysis_label, job_id)
        db.session.refresh(job)
        emit_job_failed(job.user_id, job.id, job.analysis_type.value,
                        job.error_message or str(e))
        return {'ok': False, 'reason': 'exception', 'error': str(e)}
    
@celery.task(
    name = 'analysis.run_load_flow',
    bind = True,
    soft_time_limit = 600,
    time_limit = 900,
    max_retries = 0,
)
def run_load_flow_task(self, job_id : int):
    job = db.session.get(AnalysisJob, job_id)
    if job is not None:
        job.task_id = self.request.id
        db.session.commit()
    return _run_analysis(job_id, LoadFlowService, 'load_flow')

@celery.task(
    name = 'analysis.run_short_circuit',
    bind=True,
    soft_time_limit=600,
    time_limit=900,
    max_retries=0,
)
def run_short_circuit_task(self, job_id : int):
    job = db.session.get(AnalysisJob, job_id)
    if job is not None:
        job.task_id = self.request.id
        db.session.commit()
    return _run_analysis(job_id, ShortCircuitService, 'short-circuit')


@celery.task(
    name="analysis.contingency",
    bind=True,
    soft_time_limit=1800,
    time_limit=2400,
    max_retries=0,
)
def run_contingency_task(self, job_id: int):
    job = db.session.get(AnalysisJob, job_id)
    if job is not None:
        job.task_id = self.request.id
        db.session.commit()
    return _run_analysis(job_id, ContingencyService, "contingency")

@celery.task(
    name="analysis.run_opf",
    bind=True,
    soft_time_limit=900,
    time_limit=1200,
    max_retries=0,
)
def run_opf_task(self, job_id: int):
    job = db.session.get(AnalysisJob, job_id)
    if job is not None:
        job.task_id = self.request.id
        db.session.commit()
    return _run_analysis(job_id, OPFService, "opf")


@celery.task(
    name="analysis.run_time_series",
    bind=True,
    soft_time_limit=3600,
    time_limit=4200,
    max_retries=0,
)
def run_time_series_task(self, job_id: int):
    job = db.session.get(AnalysisJob, job_id)
    if job is not None:
        job.task_id = self.request.id
        db.session.commit()
    return _run_analysis(job_id, TimeSeriesService, "time_series")


@celery.task(
    name = 'analysis.run_feasibility',
    bind = True,
    soft_time_limit = 600,
    time_limit = 900,
    max_retries = 0,
    )
def run_feasibility_task(self, study_id: int):
    study = db.session.get(FeasibilityStudy, study_id)
    if study is None:
        _log.error('feasibility study %s not found', study_id)
        return {'ok': False, 'reason': 'study not found'}
    facility = study.facility
    user_id = facility.user_id if facility else None
    if user_id:
        emit_job_progress(user_id, study.id, 1.0,'Searching for nearby substation')
    try:
        summary = FeasibilityService.run(study.id)
        if user_id:
            emit_feasibility_completed(
                user_id, study.id,
                verdict = summary['verdict'],
                summary= summary
            )
        return {'ok': True, 'study_id': study.id, 'summary': summary}
    except SoftTimeLimitExceeded:
        study.summary = 'Feasibility study exceeded time limit'
        study.completed_at= datetime.now(timezone.utc)
        db.session.commit()
        if user_id:
            emit_job_failed(user_id, study.id, 'feasibility', 'Time Limit Exceeded')
        return {'ok': False, 'reason': 'Time Limit'}
    except Exception as e:
        _log.exception('feasibility study %s failed', study_id)
        study.summary = f'Failed{e}'
        study.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        if user_id:
            emit_job_failed(user_id, study.id, 'feasibility', str(e))
        return {'ok': False, 'reason': 'exception', 'error': str(e)}

@celery.task(name = 'analysis.cancel_job', bind = True, max_retries = 0)
def cancel_job_task(self, job_id:int):
    job = db.session.get(AnalysisJob, job_id)
    if job is None:
        return {'ok': False, 'reason': 'Job not found'}
    if job.status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, AnalysisStatus.CANCELLED):
        return {'ok': False, 'reason': f'already_{job.status.value}'}
    if job.task_id:
        try:
            celery.control.revoke(job.task_id, terminate = True, signal = 'SIGTERM')
        except Exception as e:
            _log.warning('revoke failed for task %s : %s', job.task_id, e)
    job.status = AnalysisStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    emit_job_cancelled(job.user_id, job.id)
    return {'ok': True,'job_id': job.id}

