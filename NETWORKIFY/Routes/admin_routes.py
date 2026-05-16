from datetime import datetime, timedelta, timezone
from flask import Blueprint, request
from sqlalchemy import func
from extension import db
from Models import (
    Users, UserRole,
    PowerNetwork, Substation, Facility,
    AnalysisJob, AnalysisStatus, AnalysisType,
    Report,
    Plan, PlanTier, Subscription,
    AuditLog, AuditAction,
)
from ._helpers import (
    ok , fail,
    admin_required,
    get_json_body,
    require_fields,
    paginate_query
)
admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


#----------------------------------------------------------------
#--------------SYSTEM STATS--------------------------------------
#----------------------------------------------------------------

@admin_bp.get("/stats")
@admin_required
def stats():
    last_7d = datetime.now(timezone.utc) - timedelta(days= 7)
    last_30d = datetime.now(timezone.utc) - timedelta(days= 30)
    return ok(data={
        "users": { 
            "total":          Users.query.count(),
            "active":         Users.query.filter(Users.is_active.is_(True)).count(),
            "admins":         Users.query.filter(Users.role == UserRole.ADMIN).count(),
            "engineers":      Users.query.filter(Users.role == UserRole.ENGINEER).count(),
            "new_last_7d":    Users.query.filter(Users.created_at >= last_7d).count(),
            "new_last_30d":   Users.query.filter(Users.created_at >= last_30d).count(),
        },
        "networks": {
            "total":     PowerNetwork.query.count(),
            "templates": PowerNetwork.query.filter(PowerNetwork.is_template.is_(True)).count(),
        },
        "substations" : {
            "total":   Substation.query.count(),
            "public":  Substation.query.filter(Substation.is_public.is_(True)).count(),
            "private": Substation.query.filter(Substation.is_public.is_(False)).count(),
        },
        "facilities":{"total": Facility.query.count()},
        "analyses": {
            "total":     AnalysisJob.query.count(),
            "pending":   AnalysisJob.query.filter(AnalysisJob.status == AnalysisStatus.PENDING).count(),
            "running":   AnalysisJob.query.filter(AnalysisJob.status == AnalysisStatus.RUNNING).count(),
            "completed": AnalysisJob.query.filter(AnalysisJob.status == AnalysisStatus.COMPLETED).count(),
            "failed":    AnalysisJob.query.filter(AnalysisJob.status == AnalysisStatus.FAILED).count(),
            "last_7d":   AnalysisJob.query.filter(AnalysisJob.created_at >= last_7d).count(),
            "by_type": {
                t.value: AnalysisJob.query.filter(AnalysisJob.analysis_type == t).count()
                for t in AnalysisType
            },
        },
        "reports": {"total" : Report.query.count()},
        'subscriptions': {
            "total": Subscription.query.count(),
            "by_tier": {
                tier.value : (
                    db.session.query(func.count(Subscription.id)).join(Plan).filter(Plan.tier == tier).scalar() or 0)
                    for tier in PlanTier
                
            },
        }
    })

#--------------------------------------------------------------------
#---------------------AUDIT LOGS-------------------------------------
#-------------------------------------------------------------------

@admin_bp.get("/audit_logs")
@admin_required
def list_audit_logs():
    q= AuditLog.query
    if (action := request.args.get("action")):
        try:
            q= q.filter(AuditLog.action == AuditAction(action))
        except ValueError:
            return fail(f"Invalid Action :{action}", 400)
    if (uid := request.args.get("user_id")):
        try:
            q= q.filter(AuditLog.user_id == int(uid))
        except ValueError:
            return fail("user_id must be int", 400)
    if (rtype:= request.args.get("resource_type")):
        q = q.filter(AuditLog.resource_type == rtype)
    if (since:= request.args.get("since")):
        try:
            q= q.filter(AuditLog.created_at >= datetime.fromisoformat(since))
        except ValueError:
            return fail("since m,ust be ISO timestamp", 400)
    success = request.args.get("success")
    if success is not None:
        q= q.filter(AuditLog.success.is_(success.lower() == "true"))
    q = q.order_by(AuditLog.created_at.desc())
    items, meta = paginate_query(q, default_per_page=50, max_per_page=500)
    return ok(
        data= {
            "logs": [l.to_dict() for l in items]
        }, pagination = meta,
    )