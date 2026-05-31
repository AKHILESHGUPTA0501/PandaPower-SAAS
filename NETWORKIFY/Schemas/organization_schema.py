"""
Organization and member schemas.
"""
import re
from marshmallow import Schema, fields, validate, validates, ValidationError

from Models import OrgRole


_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


# =====================================================================
#  ORGANIZATION
# =====================================================================
class OrganizationSchema(Schema):
    id            = fields.Integer(dump_only=True)
    name          = fields.String()
    slug          = fields.String()
    description   = fields.String(allow_none=True)
    logo_path     = fields.String(allow_none=True)
    primary_color = fields.String(allow_none=True)
    website       = fields.String(allow_none=True)
    contact_email = fields.String(allow_none=True)
    country       = fields.String()
    is_active     = fields.Boolean()
    member_count  = fields.Integer(dump_only=True)
    created_at    = fields.String(dump_only=True)


class OrganizationCreateSchema(Schema):
    name          = fields.String(required=True, validate=validate.Length(min=1, max=160))
    slug          = fields.String(required=True, validate=validate.Length(min=2, max=80))
    description   = fields.String(required=False, allow_none=True)
    logo_path     = fields.String(required=False, allow_none=True,validate=validate.Length(max=300))
    primary_color = fields.String(required=False, allow_none=True,validate=validate.Length(max=10))
    website       = fields.String(required=False, allow_none=True,validate=validate.Length(max=200))
    contact_email = fields.Email(required=False, allow_none=True)
    contact_phone = fields.String(required=False, allow_none=True,validate=validate.Length(max=20))
    address       = fields.String(required=False, allow_none=True,validate=validate.Length(max=400))
    country       = fields.String(load_default="IN", validate=validate.Length(max=60))

    @validates("slug")
    def _slug_format(self, value, **kwargs):
        if not _SLUG_RE.match(value):
            raise ValidationError(
                "slug must be lowercase alphanumeric/hyphen, "
                "starting and ending with a letter or digit"
            )


class OrganizationUpdateSchema(Schema):
    name          = fields.String(required=False, validate=validate.Length(min=1, max=160))
    description   = fields.String(required=False, allow_none=True)
    logo_path     = fields.String(required=False, allow_none=True,validate=validate.Length(max=300))
    primary_color = fields.String(required=False, allow_none=True,validate=validate.Length(max=10))
    website       = fields.String(required=False, allow_none=True,validate=validate.Length(max=200))
    contact_email = fields.Email(required=False, allow_none=True)
    contact_phone = fields.String(required=False, allow_none=True,validate=validate.Length(max=20))
    address       = fields.String(required=False, allow_none=True,validate=validate.Length(max=400))
    country       = fields.String(required=False, validate=validate.Length(max=60))
    is_active     = fields.Boolean(required=False)


# =====================================================================
#  MEMBERSHIP
# =====================================================================
class OrganizationMemberSchema(Schema):
    id            = fields.Integer(dump_only=True)
    org_id        = fields.Integer()
    user_id       = fields.Integer()
    role          = fields.String()
    is_active     = fields.Boolean()
    invited_by_id = fields.Integer(allow_none=True)
    invited_at    = fields.String(allow_none=True)
    joined_at     = fields.String(allow_none=True)


class OrganizationMemberInviteSchema(Schema):
    """POST /organizations/<id>/members body."""
    email = fields.Email(required=True)
    role  = fields.String(
        load_default=OrgRole.MEMBER.value,
        validate=validate.OneOf([r.value for r in OrgRole]),
    )
