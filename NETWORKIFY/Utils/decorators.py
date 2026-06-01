"""
Authorisation and quota decorators.

  @admin_required        - JWT role == admin
  @engineer_required     - JWT role in {admin, engineer}
  @role_required(*roles) - generic version
  @plan_required(tier)   - user's active plan tier >= tier
  @quota_check(resource) - increment quota counter, deny if exceeded
  @require_json          - body must be valid JSON
"""

from functools import wraps
from datetime import datetime, timezone
from flask import request
from flask_jwt_extended import (
    verify_jwt_in_request,
    get_jwt,
    get_jwt_identity,
)
from extension import db
from Models import (
    Users, UserRole,
    Plan, PlanTier, Subscription, SubscriptionStatus,
    UsageQuota,
)
from .responses import fail
from .constants import FREE_TIER 


def current_user() -> Users | None:
    """Load the users row for the jwt identity"""
    try:
        verify_jwt_in_request()
    except Exception:
        return None
    uid = get_jwt_identity()
    if uid is None:
        return None
    try:
        return db.session.get(Users, int(uid))
    except (TypeError, ValueError):
        return None
    

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return fail('Missing Invalid Token', 401)
        if get_jwt().get('role') != UserRole.ADMIN.value:
            return fail('Administrator Privileges Required',403)
        return fn(*args, **kwargs)
    return wrapper


def engineer_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return fail('Missing or Invalid Token', 401)
        role = get_jwt().get('role')
        if role not in (UserRole.ADMIN.value, UserRole.ENGINEER.value):
            return fail('Engineer Privileges required',403)
        return fn(*args, **kwargs)
    return wrapper

def role_required(*roles : str):
    allowed = {r.lower() for r in roles}
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                return fail('Missing or Expired Token', 401)
            role = (get_jwt().get('role') or '').lower()
            if role not in allowed:
                return fail('Insufficient permissions',403)
            return fn(*args, **kwargs)
        return wrapper
    return  decorator


_TIER_ORDER = {
    PlanTier.FREE : 0,
    PlanTier.PRO : 1,
    PlanTier.ENTERPRISE : 2,
}

def _active_subscription_for(user : Users) -> Subscription | None:
    sub = user.subscription
    if sub is None:
        return None
    if sub.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL):
        return None
    return sub


def plan_required(min_tier : str | PlanTier):
    if isinstance(min_tier, str):
        min_tier = PlanTier(min_tier)
    min_level = _TIER_ORDER[min_tier]
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return fail('Unauthorized',401)
            if user.is_admin:
                return fn(*args, **kwargs)
            sub = _active_subscription_for(user)
            if sub is None or sub.plan is None:
                return fail(
                    f'This Feature requires the {min_tier.value} plan', 402,
                )
            if _TIER_ORDER.get(sub.plan.tier, -1) < min_level:
                return fail(
                    f'This feature requires the {min_tier.value} plan (current : {sub.plan.tier.value}',402
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def _get_or_create_current_quota(user : Users) -> UsageQuota:
    now = datetime.now(timezone.utc)
    sub = _active_subscription_for(user)
    start = (sub.current_period_start if sub and sub.current_period_start
            else now.replace(day = 1, hour= 0, minute=0, second=0, microsecond=0)
            )
    end = (sub.current_period_end if sub and sub.current_period_end
            else (start.replace(month=start.month % 12 +1)
                if start.month < 12
                else start.replace(year= start.year +1 , month= 1)))
    q = (UsageQuota.query
        .filter_by(user_id = user.id, period_start = start ).first())
    if q is None:
        q = UsageQuota(
            user_id = user.id,
            org_id = sub.org_id if sub else None,
            period_start = start,
            period_end = end,
        )
        db.session.add(q)
        db.session.flush()
    return q


_QUOTA_COUNTER_FIELD = {
    'analysis': 'analyses_used',
    "report":       "reports_used",
    "feasibility":  "feasibility_studies_used",
    "api":  'api_calls_used'
}

_QUOTA_PLAN_LIMIT_FIELD = {
    "analysis":     "max_analyses_per_month",
    "report":       "max_reports_per_month",
    "feasibility":  "max_analyses_per_month",  # share the analysis cap
    "api":          None,                       # no plan limit yet
}


def quota_check(resource : str):
    if resource not in _QUOTA_COUNTER_FIELD:
        raise ValueError(f'Unknown Quota Resource: {resource}')
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return fail('Unauthorized', 401)
            if user.is_admin:
                return fn(*args, **kwargs)
            quota = _get_or_create_current_quota(user)
            sub = _active_subscription_for(user)
            limit_field = _QUOTA_PLAN_LIMIT_FIELD.get(resource)
            if sub and sub.plan and limit_field:
                limit = getattr(sub.plan, limit_field, None)
            else :
                fallback_key = {
                    "analysis":    "max_analyses_per_month",
                    "feasibility": "max_analyses_per_month",
                    "report":      "max_reports_per_month",
                }.get(resource)
                limit = FREE_TIER.get(fallback_key) if fallback_key else None
            counter = _QUOTA_COUNTER_FIELD[resource]
            used = getattr(quota, counter, 0) or 0
            if limit is not None and used >= limit:
                return fail(
                    f'Monthly {resource} qouta exceeded ({used}/{limit})'
                    f'Upgarde your plan or wait untill next billing period',
                    429,
                    quota = {'used': used, 'limit': limit}
                )
            setattr(quota, counter, used+1)
            db.session.commit()
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_json(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            return fail('Content type must be application/json', 400)
        return fn(*args, **kwargs)
    return wrapper