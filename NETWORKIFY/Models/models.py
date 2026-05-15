"""
Users model and all shared enums.

This file purposefully contains ONLY:
  - enums used across domains
  - the Users table

Everything else (networks, substations, etc.) lives in its own
domain module under Models/.
"""
from datetime import datetime, timezone
import enum

from sqlalchemy import Enum as SAEnum
from extension import db


# ---------------------------------------------------------------------
#  ENUMS
# ---------------------------------------------------------------------
class UserRole(enum.Enum):
    ADMIN    = "admin"
    ENGINEER = "engineer"
    USER     = "user"
    VIEWER   = "viewer"


class NetworkStatus(enum.Enum):
    DRAFT    = "draft"
    SAVED    = "saved"
    ARCHIVED = "archived"


class AnalysisType(enum.Enum):
    LOAD_FLOW          = "load_flow"
    SHORT_CIRCUIT      = "short_circuit"
    CONTINGENCY        = "contingency"
    OPTIMAL_POWER_FLOW = "optimal_power_flow"
    TIME_SERIES        = "time_series"
    FEASIBILITY        = "feasibility"


class AnalysisStatus(enum.Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class FaultType(enum.Enum):
    THREE_PHASE        = "3ph"
    SINGLE_LINE_GROUND = "1ph"
    LINE_TO_LINE       = "2ph"
    DOUBLE_LINE_GROUND = "2ph_ground"


class ElementType(enum.Enum):
    BUS         = "bus"
    LINE        = "line"
    TRANSFORMER = "transformer"
    LOAD        = "load"
    GENERATOR   = "generator"
    SHUNT       = "shunt"
    EXT_GRID    = "ext_grid"
    SWITCH      = "switch"


class SeverityLevel(enum.Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


class FacilityType(enum.Enum):
    FACTORY     = "factory"
    DATA_CENTRE = "data_centre"
    WAREHOUSE   = "warehouse"
    OFFICE      = "office"
    OTHER       = "other"


class FacilitySize(enum.Enum):
    SMALL  = "small"        # <= 1 MVA
    MEDIUM = "medium"       # 1-10 MVA
    LARGE  = "large"        # 10-50 MVA
    XLARGE = "xlarge"       # > 50 MVA


class FeasibilityVerdict(enum.Enum):
    FEASIBLE              = "feasible"
    FEASIBLE_WITH_UPGRADE = "feasible_with_upgrade"
    NOT_FEASIBLE          = "not_feasible"
    INSUFFICIENT_DATA     = "insufficient_data"


class PlanTier(enum.Enum):
    FREE       = "free"
    PRO        = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(enum.Enum):
    ACTIVE   = "active"
    TRIAL    = "trial"
    EXPIRED  = "expired"
    CANCELED = "canceled"


class AuditAction(enum.Enum):
    LOGIN         = "login"
    LOGOUT        = "logout"
    CREATE        = "create"
    UPDATE        = "update"
    DELETE        = "delete"
    RUN_ANALYSIS  = "run_analysis"
    EXPORT_REPORT = "export_report"
    INVITE_MEMBER = "invite_member"


# ---------------------------------------------------------------------
#  USERS
# ---------------------------------------------------------------------
class Users(db.Model):
    """Application user."""
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50),  unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(SAEnum(UserRole), default=UserRole.USER, nullable=False)

    # Profile
    full_name      = db.Column(db.String(120), nullable=True)
    company        = db.Column(db.String(120), nullable=True)
    license_number = db.Column(db.String(60),  nullable=True)
    phone          = db.Column(db.String(20),  nullable=True)

    # Account state
    is_active              = db.Column(db.Boolean, default=True,  nullable=False)
    is_email_verified      = db.Column(db.Boolean, default=False, nullable=False)
    email_verify_token     = db.Column(db.String(128), nullable=True)
    password_reset_token   = db.Column(db.String(128), nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime,default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)

    # ---- relationships ----------------------------------------------
    networks     = db.relationship("PowerNetwork",back_populates="owner",cascade="all, delete-orphan")
    analyses     = db.relationship("AnalysisJob",back_populates="user",cascade="all, delete-orphan")
    facilities   = db.relationship("Facility",back_populates="owner",cascade="all, delete-orphan")
    reports      = db.relationship("Report",back_populates="user",cascade="all, delete-orphan")
    memberships  = db.relationship("OrganizationMember",foreign_keys="OrganizationMember.user_id",back_populates="user",cascade="all, delete-orphan")
    subscription = db.relationship("Subscription",back_populates="user",uselist=False,cascade="all, delete-orphan")
    audit_logs   = db.relationship("AuditLog",back_populates="user",cascade="all, delete-orphan")

    # ---- helpers ----------------------------------------------------
    def to_dict(self, include_email: bool = True) -> dict:
        data = {
            "id":         self.id,
            "username":   self.username,
            "role":       self.role.value,
            "full_name":  self.full_name,
            "company":    self.company,
            "is_active":  self.is_active,
            "is_email_verified": self.is_email_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        if include_email:
            data["email"] = self.email
        return data

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_engineer(self) -> bool:
        return self.role in (UserRole.ENGINEER, UserRole.ADMIN)

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"
