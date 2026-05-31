"""
Authentication and user schemas.
"""
from marshmallow import Schema, fields, validate, validates, ValidationError

from Models import UserRole


# ---------------------------------------------------------------------
#  Password validator
# ---------------------------------------------------------------------
def _validate_password(value: str) -> None:
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    if not any(c.isdigit() for c in value):
        raise ValidationError("Password must contain at least one digit")
    if not any(c.isalpha() for c in value):
        raise ValidationError("Password must contain at least one letter")


# ---------------------------------------------------------------------
#  Auth payloads
# ---------------------------------------------------------------------
class RegisterSchema(Schema):
    username       = fields.String(required=True, validate=validate.Length(min=3, max=50))
    email          = fields.Email(required=True, validate=validate.Length(max=120))
    password       = fields.String(required=True, load_only=True)
    full_name      = fields.String(required=False, validate=validate.Length(max=120))
    company        = fields.String(required=False, validate=validate.Length(max=120))
    license_number = fields.String(required=False, validate=validate.Length(max=60))
    phone          = fields.String(required=False, validate=validate.Length(max=20))

    @validates("password")
    def _password(self, value, **kwargs):
        _validate_password(value)


class LoginSchema(Schema):
    email    = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class ChangePasswordSchema(Schema):
    current_password = fields.String(required=True, load_only=True)
    new_password     = fields.String(required=True, load_only=True)

    @validates("new_password")
    def _password(self, value, **kwargs):
        _validate_password(value)


class ForgotPasswordSchema(Schema):
    email = fields.Email(required=True)


class ResetPasswordSchema(Schema):
    token        = fields.String(required=True, validate=validate.Length(min=20, max=128))
    new_password = fields.String(required=True, load_only=True)

    @validates("new_password")
    def _password(self, value, **kwargs):
        _validate_password(value)


# ---------------------------------------------------------------------
#  User output / update
# ---------------------------------------------------------------------
class UserSchema(Schema):
    """Public user representation — never includes password_hash."""
    id        = fields.Integer(dump_only=True)
    username  = fields.String()
    email     = fields.Email()
    role      = fields.String()
    full_name = fields.String(allow_none=True)
    company   = fields.String(allow_none=True)
    license_number = fields.String(allow_none=True)
    phone     = fields.String(allow_none=True)
    is_active = fields.Boolean()
    is_email_verified = fields.Boolean()
    created_at = fields.String(allow_none=True)
    last_login = fields.String(allow_none=True)


class UserUpdateSchema(Schema):
    """Self-service profile update."""
    full_name      = fields.String(required=False, validate=validate.Length(max=120))
    company        = fields.String(required=False, validate=validate.Length(max=120))
    license_number = fields.String(required=False, validate=validate.Length(max=60))
    phone          = fields.String(required=False, validate=validate.Length(max=20))
    # admin-only fields are accepted but the route enforces the gate
    role           = fields.String(
        required=False,
        validate=validate.OneOf([r.value for r in UserRole]),
    )
    is_active         = fields.Boolean(required=False)
    is_email_verified = fields.Boolean(required=False)
