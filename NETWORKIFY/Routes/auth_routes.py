import secrets
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity
)
from extension import db, bcrypt
from Models import Users, UserRole
from ._helpers import (
    ok, fail,
    current_user, 
    get_json_body,
    require_fields,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

#--------------------------------------------------------
#------------HELPERS------------------------------------
#---------------------------------------------------------

def _issue_tokens(user: Users)-> dict:
    additional= {"role": user.role.value, "username": user.username}
    return {
        "access_token": create_access_token(identity= str(user.id), additional_claims= additional),
        "refresh_token": create_access_token(identity= str(user.id), additional_claims= additional),
    }

def _validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "password must be atleast 8 characters long"
    if not any(c.isdigit() for c in password):
        return "Password Must Contain One Digit"
    if not any(c.isalpha() for c in password):
        return "Password must Contain at least One letter"
    return None

#------------------------------------------------
#--------------REGISTER-------------------------
#----------------------------------------------

@auth_bp.post("/register")
def register():
    data = get_json_body()
    missing, err = require_fields(data, ['username', 'email', 'password'])
    if err:
        return err
    username = data['username'].strip()
    email = data['email'].strip()
    password = data['password']
    if not (3 <= len(username) <= 50):
        return fail('Username must be 3-50 characters',400)
    if "@" not in email or '.' not in email:
        return fail("Invalid email format",400)
    pw_err= _validate_password(password)
    if pw_err:
        return fail(pw_err, 400)
    if Users.query.filter(
        (Users.username == username) | (Users.email == email)
    ).first():
        return fail("Username or email already exist",409)
    user = Users(
        username = username,
        email = email,
        password = bcrypt.generate_password_hash(password).decode('utf-8'),
        full_name = data.get('full_name'),
        company        = data.get("company"),
        license_number = data.get("license_number"),
        phone          = data.get("phone"),
        role           = UserRole.USER,
        created_at     = datetime.now(timezone.utc),
    )
    db.session.add(user)
    db.session.commit()
    tokens = _issue_tokens(user)
    return ok(
        data= {"user": user.to_dict(), **tokens},
        message= "Account created Successfully",
        status=201
    )

#---------------------------------------------------------------
#-------------LOGIN---------------------------------------------
#---------------------------------------------------------------

@auth_bp.post('/login')
def login():
    data = get_json_body()
    _, err = require_fields(data, ['email', 'password'])
    if err:
        return err
    email = data['email'].strip().lower()
    password = data['password']
    user = Users.query.filter_by(email = email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return fail('Invalid email or password')
    if not user.is_active:
        return fail("Account deactivated , Please Contact Admin")
    user.last_login= datetime.now(timezone.utc)
    db.session.commit()
    tokens = _issue_tokens(user)
    return ok(
        data = {"user": user.to_dict(), **tokens},
        message= "Login Successful"
    )

#-------------------------------------------------------------
#-------------ME------------------------------------------------
#--------------------------------------------------------------
@auth_bp.get('/me')
@jwt_required()
def me():
    user = current_user()
    if user is None:
        return fail('User not found', 404)
    return ok(data={"user": user.to_dict()})

@auth_bp.patch('/me')
@jwt_required()
def me():
    user = current_user()
    if user is None:
        return fail('User not Found',404)
    data = get_json_body()
    editable = {'full_name', 'company', 'license number', 'phone'}
    for k, v in data.items():
        if k in editable:
            setattr(user, k,v)
    user.updated_at= datetime.now(timezone.utc)
    db.session.commit()
    return ok(data = {'user': user.to_dict()}, message= "Profile Updated")

@auth_bp.post('/logout')
@jwt_required(optional= True)
def logout():
    ##Stateless JWT — client just discards token.
    # For real revocation, store JTI in Redis blocklist (TODO).
    return ok(message="Logged out successfully")
        
@auth_bp.post('/refresh')
@jwt_required(refresh= True)
def refresh():
    uid = get_jwt_identity()
    user = db.session.get(Users, int(uid))
    if user is None or not user.is_active:
        return fail("User not found or inactive",401)
    access_token = create_access_token(
        identity= str(user.id),
        additional_claims= {'role': user.role.value, "username": user.username},
    )
    return ok(data = {"access_token": access_token})

@auth_bp.post("/change-password")
@jwt_required()
def change_password():
    user = current_user()
    if user is None:
        return fail("User not Found",404)
    data = get_json_body()
    _, err = require_fields(data, ['current_password','new_password'])
    if err:
        return err
    if not bcrypt.check_password_hash(user.password_hash, data['current_password']):
        return fail("Current password is incorrect",401)
    pw_err= _validate_password(data['new_password'])
    if pw_err:
        return fail(pw_err,400)
    user.password_hash = bcrypt.generate_password_hash(
        data['new_password']
    ).decode('utf-8')
    user.updated_at= datetime.now(timezone.utc)
    db.session.commit()
    return ok(message="password Updated")

@auth_bp.post('/forgot_password')
def forgot_password():
    data = get_json_body()
    email = (data.get("email") or "").strip().lower()
    if not email:
        return fail("Email is required",400)
    user = Users.query.filter_by(email = email).first()
    if user and user.is_active:
        user.password_reset_token = secrets.token_urlsafe(32)
        user.password_reset_expires= (
            datetime.now(timezone.utc) + timedelta(hours =1)
        )
        db.session.commit()
        from flask import current_app
        extra = {}
        if current_app.config.get('DEBUG'):
            extra['debug_reset_token'] = user.password_reset_token
        return ok(
            message="If the email already exists a reset link will be sent"
            **extra
        )
    return ok(
        message= 'If the email already exists a reset link will be sent'
    )


@auth_bp.post('/reset-password')
def reset_password():
    data = get_json_body()
    _, err = require_fields(data, ['token', 'new_password'])
    if err:
        return err
    user = Users.query.filter_by(password_reset_token = data['token']).first()
    if ( user is None
        or user.password_reset_expires is None 
        or user.password_reset_expires < datetime.now(timezone.utc)):
        return fail('Invalid or expired reset token',400)
    pw_err = _validate_password(data['new_password'])
    if pw_err:
        return fail(pw_err,400)
    user.password_hash = bcrypt.generate_password_hash(
        data['new_password']
    ).decode('utf-8')
    user.password_reset_token = None
    user.password_reset_expires = None
    user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(message= "Password has been reset")