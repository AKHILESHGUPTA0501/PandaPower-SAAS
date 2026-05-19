"""
User routes.

Endpoints
---------
GET    /api/users               List users (admin)
GET    /api/users/<id>          Get user by id (admin or self)
PATCH  /api/users/<id>          Update user (admin or self)
DELETE /api/users/<id>          Deactivate user (admin)
POST   /api/users/<id>/activate Re-activate user (admin)
"""
from datetime import datetime, timezone

from flask import Blueprint
from flask_jwt_extended import jwt_required

from extension import db
from Models import Users, UserRole
from ._helpers import (
    ok, fail,
    current_user,
    admin_required,
    get_json_body,
    paginate_query,
)


user_bp = Blueprint("users", __name__, url_prefix="/api/users")


# ---------------------------------------------------------------------
#  GET /  (admin)
# ---------------------------------------------------------------------
@user_bp.get("/")
@admin_required
def list_users():
    from flask import request
    q = Users.query
    role = request.args.get("role")
    if role:
        try:
            q = q.filter(Users.role == UserRole(role))
        except ValueError:
            return fail(f"Invalid role: {role}", 400)
    search = request.args.get("q")
    if search:
        like = f"%{search}%"
        q = q.filter((Users.username.ilike(like)) | (Users.email.ilike(like)))
    q = q.order_by(Users.created_at.desc())
    items, meta = paginate_query(q)
    return ok(
        data={"users": [u.to_dict() for u in items]},
        pagination=meta,
    )


# ---------------------------------------------------------------------
#  GET /<id>  (admin or self)
# ---------------------------------------------------------------------
@user_bp.get("/<int:user_id>")
@jwt_required()
def get_user(user_id: int):
    me = current_user()
    if me is None:
        return fail("Unauthorized", 401)
    if me.id != user_id and not me.is_admin:
        return fail("Forbidden", 403)
    user = db.session.get(Users, user_id)
    if user is None:
        return fail("User not found", 404)
    return ok(data={"user": user.to_dict()})


# ---------------------------------------------------------------------
#  PATCH /<id>  (admin or self)
# ---------------------------------------------------------------------
@user_bp.patch("/<int:user_id>")
@jwt_required()
def update_user(user_id: int):
    me = current_user()
    if me is None:
        return fail("Unauthorized", 401)
    if me.id != user_id and not me.is_admin:
        return fail("Forbidden", 403)
    user = db.session.get(Users, user_id)
    if user is None:
        return fail("User not found", 404)

    data = get_json_body()
    self_editable  = {"full_name", "company", "license_number", "phone"}
    admin_editable = self_editable | {"role", "is_active", "is_email_verified"}
    allowed = admin_editable if me.is_admin else self_editable

    for k, v in data.items():
        if k not in allowed:
            continue
        if k == "role":
            try:
                v = UserRole(v)
            except ValueError:
                return fail(f"Invalid role: {v}", 400)
        setattr(user, k, v)
    user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(data={"user": user.to_dict()}, message="User updated")


# ---------------------------------------------------------------------
#  DELETE /<id>  (admin) - soft deactivate
# ---------------------------------------------------------------------
@user_bp.delete("/<int:user_id>")
@admin_required
def deactivate_user(user_id: int):
    user = db.session.get(Users, user_id)
    if user is None:
        return fail("User not found", 404)
    if user.is_admin:
        # Don't allow deactivating the last admin
        remaining_admins = Users.query.filter(
            Users.role == UserRole.ADMIN,
            Users.is_active.is_(True),
            Users.id != user.id,
        ).count()
        if remaining_admins == 0:
            return fail("Cannot deactivate the last active admin", 400)
    user.is_active  = False
    user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(message="User deactivated")


# ---------------------------------------------------------------------
#  POST /<id>/activate  (admin)
# ---------------------------------------------------------------------
@user_bp.post("/<int:user_id>/activate")
@admin_required
def activate_user(user_id: int):
    user = db.session.get(Users, user_id)
    if user is None:
        return fail("User not found", 404)
    user.is_active  = True
    user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(message="User activated", data={"user": user.to_dict()})
