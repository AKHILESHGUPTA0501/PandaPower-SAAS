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

@admin_bp.get("/users/recent")
@admin_required
def recent_users():
    try:
        days = max(1, min(int(request.args.get("days"), 30)),365)
    except ValueError:
        days = 30
    since = datetime.now(timezone.utc) - timedelta(days= days)
    users= (Users.query.filter(
        Users.created_at >= since
    ).order_by(Users.created_at.desc()).all())
    return ok(data = {
        "count": len(users),
        "days": days,
        "users": [u.to_dict for u in users]

    })

@admin_bp.post("/plans")
@admin_required
def create_plan():
    data = get_json_body()
    _, err = require_fields(data, ['tier',"name"])
    if err:
        return err
    try:
        tier = PlanTier(data["tier"])
    except ValueError:
        return fail(f"Invalid tier: {data['tier']}",400)
    if Plan.query.filter_by(tier = tier).first():
        return fail(f"Plan with tier '{tier.value}' already exist", 409)
    plan = Plan(
        tier        = tier,
        name        = data["name"].strip(),
        description = data.get("description"),
        price_inr_per_month = data.get("price_inr_per_month"),
        price_inr_per_year  = data.get("price_inr_per_year"),
        max_networks            = data.get("max_networks"),
        max_buses_per_network   = data.get("max_buses_per_network"),
        max_analyses_per_month  = data.get("max_analyses_per_month"),
        max_reports_per_month   = data.get("max_reports_per_month"),
        max_facilities          = data.get("max_facilities"),
        max_org_members         = data.get("max_org_members"),
        allows_contingency      = bool(data.get("allows_contingency",      False)),
        allows_opf              = bool(data.get("allows_opf",              False)),
        allows_timeseries       = bool(data.get("allows_timeseries",       False)),
        allows_pdf_branding     = bool(data.get("allows_pdf_branding",     False)),
        allows_api_access       = bool(data.get("allows_api_access",       False)),
        allows_priority_compute = bool(data.get("allows_priority_compute", False)),
        is_active   = bool(data.get("is_active", True)),
    )
    db.session.add(Plan)
    db.session.commit()
    return ok(data = {'Plan': plan.to_dict()}, message= "Plan Created", status= 201)

@admin_bp.patch("/plans/<int: plan_id>")
@admin_required()
def update_plan(plan_id : int):
    plan = db.session.get(Plan, plan_id)
    if plan is None:
        return fail("Plan Not Found",404)
    data = get_json_body()
    editable = {
        "name", "description",
        "price_inr_per_month", "price_inr_per_year",
        "max_networks", "max_buses_per_network",
        "max_analyses_per_month", "max_reports_per_month",
        "max_facilities", "max_org_members",
        "allows_contingency", "allows_opf", "allows_timeseries",
        "allows_pdf_branding", "allows_api_access", "allows_priority_compute",
        "is_active",
    }
    for k, v in data.items():
        if k in editable:
            setattr(plan, k, v)
    db.session.commit()
    return ok(data = {"plan": plan.to_dict(0)}, message= "Plan Updated")

@admin_bp.delete('/plans/<int:plan_id>')
@admin_required
def deactivate_plan(plan_id : int):
    plan = db.session.get(Plan, plan_id)
    if plan is None:
        return fail("Plan Not Found", 404)
    plan.is_active= False
    db.session.commit()
    return ok(message= "Plan Deactivated")

@admin_bp.get('/jobs/active')
@admin_required
def active_jobs():
    jobs = (AnalysisJob.query.filter(AnalysisJob.status.in_(
            [AnalysisStatus.PENDING, AnalysisStatus.RUNNING]))
            .order_by(AnalysisJob.created_at.asc()).all())
    return ok(data = {
        "count": len(jobs),
        "jobs": [j.to_dict() for j in jobs],
    })