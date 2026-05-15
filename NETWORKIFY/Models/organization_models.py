"""
Organization / project / team domain.

A consulting firm signs up as an Organization. Engineers join via
OrganizationMember (with a role). Networks, facilities, and
substations can be scoped to an Organization for sharing.

NAMING NOTE
-----------
The underlying table is named ``projects`` (since network_models and
substation_models reference ``projects.id``) and the class is
``Organization``. A module-level alias ``Project = Organization`` is
exported for callers that prefer that name.
"""
import enum
import secrets
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum
from extension import db


class OrgRole(enum.Enum):
    OWNER  = "owner"      # full control, billing
    ADMIN  = "admin"      # manage members, settings
    MEMBER = "member"     # create / run analyses
    VIEWER = "viewer"     # read-only


class Organization(db.Model):
    """
    A consulting firm / project workspace. Multiple users join via
    OrganizationMember rows.
    """
    __tablename__ = "projects"   # historical table name kept for FK compatibility

    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(160), nullable=False, index=True)
    slug         = db.Column(db.String(80),  unique=True, nullable=False, index=True)
    description  = db.Column(db.Text, nullable=True)

    # Branding (used on PDF reports)
    logo_path     = db.Column(db.String(300), nullable=True)
    primary_color = db.Column(db.String(10),  nullable=True)

    # Contact
    website       = db.Column(db.String(200), nullable=True)
    contact_email = db.Column(db.String(120), nullable=True)
    contact_phone = db.Column(db.String(20),  nullable=True)
    address       = db.Column(db.String(400), nullable=True)
    country       = db.Column(db.String(60),  default="IN")

    is_active     = db.Column(db.Boolean, default=True)

    # Invitation
    invite_code   = db.Column(db.String(32), unique=True, nullable=True)

    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = db.Column(db.DateTime,default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc))

    members      = db.relationship("OrganizationMember",foreign_keys="OrganizationMember.org_id",back_populates="organization",cascade="all, delete-orphan")
    networks     = db.relationship("PowerNetwork", back_populates="project")
    facilities   = db.relationship("Facility",     back_populates="project")
    substations  = db.relationship("Substation",   back_populates="project")
    subscription = db.relationship("Subscription",back_populates="organization",uselist=False,cascade="all, delete-orphan")

    # ---- helpers -----------------------------------------------------
    def rotate_invite_code(self) -> str:
        self.invite_code = secrets.token_urlsafe(16)
        return self.invite_code

    def to_dict(self):
        return {
            "id":            self.id,
            "name":          self.name,
            "slug":          self.slug,
            "description":   self.description,
            "logo_path":     self.logo_path,
            "primary_color": self.primary_color,
            "website":       self.website,
            "contact_email": self.contact_email,
            "country":       self.country,
            "is_active":     self.is_active,
            "member_count":  len(self.members),
            "created_at":    self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Organization {self.name}>"


# Backward-compatible alias.
Project = Organization


class OrganizationMember(db.Model):
    """Membership of one User in one Organization with a role."""
    __tablename__ = "organization_members"

    id            = db.Column(db.Integer, primary_key=True)
    org_id        = db.Column(db.Integer, db.ForeignKey("projects.id"),nullable=False, index=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"),nullable=False, index=True)
    role          = db.Column(SAEnum(OrgRole),default=OrgRole.MEMBER, nullable=False)
    is_active     = db.Column(db.Boolean, default=True)
    invited_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    invited_at    = db.Column(db.DateTime, nullable=True)
    joined_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    organization = db.relationship("Organization",foreign_keys=[org_id],back_populates="members")
    user         = db.relationship("Users",foreign_keys=[user_id],back_populates="memberships")
    invited_by   = db.relationship("Users", foreign_keys=[invited_by_id])

    __table_args__ = (
        db.UniqueConstraint("org_id", "user_id", name="uq_org_member"),
    )

    def to_dict(self):
        return {
            "id":            self.id,
            "org_id":        self.org_id,
            "user_id":       self.user_id,
            "role":          self.role.value,
            "is_active":     self.is_active,
            "invited_by_id": self.invited_by_id,
            "invited_at":    self.invited_at.isoformat() if self.invited_at else None,
            "joined_at":     self.joined_at.isoformat()  if self.joined_at  else None,
        }
