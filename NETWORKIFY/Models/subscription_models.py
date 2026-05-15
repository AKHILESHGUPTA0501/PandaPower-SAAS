"""
SaaS subscription scaffolding.

NOTE: This is modelled in the database for completeness, but no real
payment processor is integrated. The decorator `@plan_required` in
Utils.decorators reads from these tables to gate features behind
plan tiers.

Quota is tracked per-user (and optionally per-org) per period.
"""
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum
from extension import db
from .models import PlanTier, SubscriptionStatus


# ---------------------------------------------------------------------
#  PLAN  (catalogue entry, seeded by scripts/seed_plans.py)
# ---------------------------------------------------------------------
class Plan(db.Model):
    __tablename__ = "plans"

    id           = db.Column(db.Integer, primary_key=True)
    tier         = db.Column(SAEnum(PlanTier), unique=True, nullable=False)
    name         = db.Column(db.String(80), nullable=False)
    description  = db.Column(db.Text, nullable=True)

    # Pricing (display-only; nothing is actually billed)
    price_inr_per_month = db.Column(db.Float, nullable=True)
    price_inr_per_year  = db.Column(db.Float, nullable=True)

    # Limits (NULL = unlimited)
    max_networks            = db.Column(db.Integer, nullable=True)
    max_buses_per_network   = db.Column(db.Integer, nullable=True)
    max_analyses_per_month  = db.Column(db.Integer, nullable=True)
    max_reports_per_month   = db.Column(db.Integer, nullable=True)
    max_facilities          = db.Column(db.Integer, nullable=True)
    max_org_members         = db.Column(db.Integer, nullable=True)

    # Feature flags
    allows_contingency      = db.Column(db.Boolean, default=False)
    allows_opf              = db.Column(db.Boolean, default=False)
    allows_timeseries       = db.Column(db.Boolean, default=False)
    allows_pdf_branding     = db.Column(db.Boolean, default=False)
    allows_api_access       = db.Column(db.Boolean, default=False)
    allows_priority_compute = db.Column(db.Boolean, default=False)

    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    subscriptions = db.relationship("Subscription", back_populates="plan")

    def to_dict(self):
        return {
            "id":          self.id,
            "tier":        self.tier.value,
            "name":        self.name,
            "description": self.description,
            "price_inr_per_month": self.price_inr_per_month,
            "price_inr_per_year":  self.price_inr_per_year,
            "limits": {
                "max_networks":           self.max_networks,
                "max_buses_per_network":  self.max_buses_per_network,
                "max_analyses_per_month": self.max_analyses_per_month,
                "max_reports_per_month":  self.max_reports_per_month,
                "max_facilities":         self.max_facilities,
                "max_org_members":        self.max_org_members,
            },
            "features": {
                "contingency":      self.allows_contingency,
                "opf":              self.allows_opf,
                "timeseries":       self.allows_timeseries,
                "pdf_branding":     self.allows_pdf_branding,
                "api_access":       self.allows_api_access,
                "priority_compute": self.allows_priority_compute,
            },
            "is_active":   self.is_active,
        }

    def __repr__(self):
        return f"<Plan {self.tier.value}>"


# ---------------------------------------------------------------------
#  SUBSCRIPTION  (one row per user OR per org)
# ---------------------------------------------------------------------
class Subscription(db.Model):
    """
    Active subscription. Exactly one of user_id / org_id should be set.
    """
    __tablename__ = "subscriptions"

    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=True, unique=True, index=True)
    org_id  = db.Column(db.Integer, db.ForeignKey("projects.id"),
                        nullable=True, unique=True, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"),
                        nullable=False, index=True)
    status  = db.Column(SAEnum(SubscriptionStatus),
                        default=SubscriptionStatus.TRIAL, nullable=False)

    started_at           = db.Column(db.DateTime,default=lambda: datetime.now(timezone.utc))
    current_period_start = db.Column(db.DateTime,default=lambda: datetime.now(timezone.utc))
    current_period_end   = db.Column(db.DateTime, nullable=True)
    trial_ends_at        = db.Column(db.DateTime, nullable=True)
    canceled_at          = db.Column(db.DateTime, nullable=True)

    # Placeholders for when payments are wired up
    external_subscription_id = db.Column(db.String(120), nullable=True)
    external_customer_id     = db.Column(db.String(120), nullable=True)

    user         = db.relationship("Users",        back_populates="subscription")
    organization = db.relationship("Organization", back_populates="subscription")
    plan         = db.relationship("Plan",         back_populates="subscriptions")

    __table_args__ = (
        db.CheckConstraint(
            "(user_id IS NOT NULL) <> (org_id IS NOT NULL)",
            name="ck_subscription_one_owner",
        ),
    )

    @property
    def is_active(self) -> bool:
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)

    def to_dict(self):
        return {
            "id":      self.id,
            "user_id": self.user_id,
            "org_id":  self.org_id,
            "plan_id": self.plan_id,
            "plan":    self.plan.to_dict() if self.plan else None,
            "status":  self.status.value,
            "started_at":           self.started_at.isoformat()           if self.started_at           else None,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end":   self.current_period_end.isoformat()   if self.current_period_end   else None,
            "trial_ends_at":        self.trial_ends_at.isoformat()        if self.trial_ends_at        else None,
        }


# ---------------------------------------------------------------------
#  USAGE QUOTA  (counters reset each billing period)
# ---------------------------------------------------------------------
class UsageQuota(db.Model):
    """
    Per-user usage counters reset at the start of each billing period.
    The decorator `@quota_check(resource)` increments the appropriate
    counter when the user runs an action.
    """
    __tablename__ = "usage_quotas"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"),nullable=False, index=True)
    org_id       = db.Column(db.Integer, db.ForeignKey("projects.id"),nullable=True, index=True)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end   = db.Column(db.DateTime, nullable=False)

    analyses_used            = db.Column(db.Integer, default=0)
    reports_used             = db.Column(db.Integer, default=0)
    feasibility_studies_used = db.Column(db.Integer, default=0)
    api_calls_used           = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime,default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship("Users", foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint("user_id", "period_start", name="uq_quota_user_period"),
        db.Index("ix_quota_user_period", "user_id", "period_start", "period_end"),
    )

    def to_dict(self):
        return {
            "id":      self.id,
            "user_id": self.user_id,
            "org_id":  self.org_id,
            "period_start": self.period_start.isoformat(),
            "period_end":   self.period_end.isoformat(),
            "analyses_used":            self.analyses_used,
            "reports_used":             self.reports_used,
            "feasibility_studies_used": self.feasibility_studies_used,
            "api_calls_used":           self.api_calls_used,
        }
