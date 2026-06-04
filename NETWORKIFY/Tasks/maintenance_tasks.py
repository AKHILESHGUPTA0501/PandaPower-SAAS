"""
Periodic maintenance Celery tasks.

Wire these in celery beat schedule. Example (in extension.py or
config):

    celery.conf.beat_schedule = {
        "reset-monthly-quotas": {
            "task":     "maintenance.reset_monthly_quotas",
            "schedule": crontab(day_of_month=1, hour=0, minute=5),
        },
        "purge-audit-logs": {
            "task":     "maintenance.purge_old_audit_logs",
            "schedule": crontab(hour=2, minute=0),
        },
        "cleanup-expired-tokens": {
            "task":     "maintenance.cleanup_expired_tokens",
            "schedule": crontab(hour=3, minute=0),
        },
        "cleanup-old-reports": {
            "task":     "report.cleanup_old",
            "schedule": crontab(hour=4, minute=0),
        },
        "health-check": {
            "task":     "maintenance.health_check",
            "schedule": 300.0,    # every 5 minutes
        },
    }
"""
from datetime import timedelta, datetime, timezone
from sqlalchemy import func
from extension import celery, db
from Models import    (Users,
    AuditLog,
    UsageQuota,
    AnalysisJob, AnalysisStatus,
    Subscription, SubscriptionStatus,
)
from Utils.logger import get_logger


_log = get_logger(__name__)



@celery.task(name = 'maintenance.cleanup_expired_tokens', bind = True, max_retries = 0)
def cleanup_expired_tokens_task(self):
    now = datetime.now(timezone.utc)
    expired = (Users.query
               .filter(Users.password_reset_expires.isnot(None))
               .filter(Users.password_reset_expires < now)
               .all())
    for u in expired:
        u.password_reset_token = None
        u.password_reset_expires = None
    db.session.commit()
    return {'ok': True, 'cleared':len(expired)}



@celery.task(name = 'maintenance.reset_monthly_quotas', bind = True, max_retries = 0)
def reset_monthly_quotas_task(self):
    now = datetime.now(timezone.utc)
    next_month = (now.replace(month = now.month %12 +1 , day = 1, hour = 0, minute = 0, second = 0, microsecond = 0)
                if now.month < 12
                else now.replace(year = now.year + 1,month=1, day=1,hour=0, minute=0, second=0, microsecond=0))
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) 
    active = (Subscription.query.filter(Subscription.status.in_([
            SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL
    ])).all())
    for sub in active:
        user_ids = [sub.user_id] if sub.user_id else [
            m.user_id for m in (sub.organization.members if sub.organization else [])
        ]
        for uid in user_ids:
            if not uid:
                continue
            exist = (UsageQuota.query.filter_by(user_id = uid, period_start = period_start).first())
            if exist:
                continue
            db.session.add(UsageQuota(
                user_id = uid,
                org_id = sub.org_id,
                period_start = period_start,
                period_end = next_month,
            ))
            created += 1
    db.session.commit()
    return{
        "ok": True,
        "subscriptions_rolled": len(active),
        "quotas_created":       created,
        "period_start":         period_start.isoformat(),
        "period_end":            next_month.isoformat(),
    }



@celery.task(name = 'maintenence.purge_old_audit_logs', bind = True, max_retries = 0)
def purge_old_audit_logs(self, retention_days: int = 365):
    cutoff = datetime.now(timezone.utc) - timedelta(days= retention_days)
    deleted = (db.session.query(AuditLog)
               .filter(AuditLog.created_at < cutoff)
               .delete(synchronize_session= False))
    db.session.commit()
    return {'ok': True, 'deleted': int(deleted), 'retention_days': retention_days}



@celery.task(name = 'maintenance.health_check', bind = True, max_retries = 0)
def health_check_task(self):
    now = datetime.now(timezone.utc)
    stuck_cutoff = now - timedelta(hours= 2)
    stuck = ( AnalysisJob.query
             .filter(AnalysisJob.status == AnalysisStatus.RUNNING)
             .filter(AnalysisJob.started_at.isnot(None))
             .filter(AnalysisJob.started_at < stuck_cutoff)
             .all())
    for j in stuck:
        j.status = AnalysisStatus.FAILED
        j.error_message = 'Worker died or job stalled (> 2h running)'
        j.completed_at = now
    db.session.commit()
    pending_count = AnalysisJob.query.filter_by(
        status = AnalysisStatus.PENDING
    ).count()
    running_count = AnalysisJob.query.filter_by(
        status = AnalysisStatus.RUNNING
    ).count()
    return {
        "ok":            True,
        "timestamp":     now.isoformat(),
        "stuck_swept":   len(stuck),
        "pending_jobs":  int(pending_count),
        "running_jobs":  int(running_count),
    }