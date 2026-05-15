"""
Audit trail.

Every state-changing action goes through ``Utils.audit.log_action()``
which inserts an AuditLog row. Used for security, compliance, and
operational debugging.
"""
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum
from extension import db
from .models import AuditAction


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=True, index=True)
    org_id  = db.Column(db.Integer, db.ForeignKey("projects.id"),
                        nullable=True, index=True)

    action        = db.Column(SAEnum(AuditAction), nullable=False, index=True)
    # The thing being acted on, e.g. "power_network", "facility", "analysis_job"
    resource_type = db.Column(db.String(60), nullable=True, index=True)
    resource_id   = db.Column(db.Integer,    nullable=True, index=True)

    # Request metadata
    ip_address   = db.Column(db.String(45),  nullable=True)   # IPv6-safe
    user_agent   = db.Column(db.String(300), nullable=True)
    http_method  = db.Column(db.String(10),  nullable=True)
    http_path    = db.Column(db.String(300), nullable=True)
    status_code  = db.Column(db.Integer,     nullable=True)

    # Free-form context as JSON
    details_json = db.Column(db.Text, nullable=True)

    success       = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text,    nullable=True)

    created_at = db.Column(db.DateTime,default=lambda: datetime.now(timezone.utc),index=True)

    user = db.relationship("Users", back_populates="audit_logs")

    __table_args__ = (
        db.Index("ix_audit_user_created", "user_id", "created_at"),
        db.Index("ix_audit_resource",     "resource_type", "resource_id"),
    )

    def to_dict(self):
        return {
            "id":            self.id,
            "user_id":       self.user_id,
            "org_id":        self.org_id,
            "action":        self.action.value,
            "resource_type": self.resource_type,
            "resource_id":   self.resource_id,
            "ip_address":    self.ip_address,
            "http_method":   self.http_method,
            "http_path":     self.http_path,
            "status_code":   self.status_code,
            "success":       self.success,
            "error_message": self.error_message,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return (f"<AuditLog user={self.user_id} {self.action.value} "
                f"{self.resource_type}:{self.resource_id}>")
