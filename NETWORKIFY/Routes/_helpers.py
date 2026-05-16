from functools import wraps
from typing import Any

from flask import jsonify, request
from flask_jwt_extended import (
    verify_jwt_in_request,
    get_jwt_identity,
    get_jwt,
)
from extension import db
from Models import Users, UserRole


def ok(data: Any=None, message: str= "OK", status: int = 200, **extra):
    payload = {'success':True, "message" : message}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload), status

def fail(message: str, status: int = 400, **extra):
    payload = {"success":False, "message": message}
    payload.update(extra)
    return jsonify(payload), status

#---------------------------------------------------------
#---------AUTHENTICATION HELPER---------------------------
#---------------------------------------------------------

def current_user() -> Users | None:
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
    
def require_user():
    user = current_user()
    if user is None:
        return None, fail("User Not Found", 401)
    if not user.is_active:
        return None, fail("Account is Deactivated", 403)
    return user, None

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return fail("Missing or Invalid token",401)
        claims = get_jwt()
        if claims.get("role") != UserRole.ADMIN.value:
            return fail("Administrator privileges required", 403)
        return fn(*args, **kwargs)
    return wrapper

def role_required(*roles: str):
    allowed = {r.lower() for r in roles}
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                return fail("Missing or Invalid Token", 401)
            role = (get_jwt().get("role") or "").lower()
            if role not in allowed:
                return fail("Insufficient permissions", 403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def get_json_body() -> dict:
    return request.get_json(silent= True) or {}


def require_fields(data: dict, fields: list[str]):
    missing = [ f for f in fields if not data.get(f)]
    if missing:
        return missing, fail(
            f"Missing required Fields: {','.join(missing)}",
            400,
            missing_fields = missing,
        )
    return None, None

def paginate_query(query, default_per_page : int=20,max_per_page : int = 100):
    try:
        page = max(1, int(request.args.get("page",1)))
    except (TypeError, ValueError):
        page= 1
    try:
        per_page = int(request.args.get("per_page", default_per_page))
    except (TypeError, ValueError):
        per_page =  default_per_page
    per_page = max(1, min(per_page, max_per_page))

    total = query.count()
    items = query.offset((page -1)*per_page).limit(per_page).all()
    meta = {
        "page": page,
        "per_page": per_page ,
        "total": total,
        "pages": (total + per_page -1)// per_page,
    }
    return items, meta
