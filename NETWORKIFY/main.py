import os 
import click
from datetime import datetime, timezone
from flask import Flask, Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from dotenv import load_dotenv
from config import config_map
from extension import db, jwt, socketio, bcrypt, init_extensions
from Models.models import Users, UserRole


load_dotenv()

def create_app()-> Flask:
    app = Flask(__name__)
    env = os.getenv("FLASK_ENV", "development")
    app.config.from_object(config_map.get(env, config_map["development"]))
    init_extensions(app)
    app.register_blueprint(auth_bp, url_prefix = "/api/auth")
    register_cli(app)
    return app

def register_cli(app: Flask):
    @app.cli.command("create_db")
    def create_db():
        db.create_all()
        click.echo("✈️ Database Tables Created")
    @app.cli.command("drop_db")
    @click.confirmation_option(prompt = "😰 This delete all existing data, Are you sure?")
    def drop_db():
        db.drop_all()
        click.echo("^_^ All tables are Dropped")
    @app.cli.command("create-admin")
    @click.option("--username",prompt = "Admin username")
    @click.option("--email", prompt = "Admin email")
    @click.option("--password", prompt = "Admin Password", hide_input = True, confirmation_prompt = True)
    def create_admin(username, email, password):
        if Users.query.filter(
            (Users.username == username) |  (Users.email == email)
        ).first():
            click.echo(" 😞 Username or Email already exists")
            return
        admin = Users(
            username = username,
            email = email,
            password_hash = bcrypt.generate_password_hash(password).decode("utf-8"),
            role = UserRole.ADMIN,
            is_active = True,
            created_at = datetime.now(timezone.utc),

        )
        db.session.add(admin)
        db.session.commit()
        click.echo(f"✅ Admin '{username}' created")
    app.cli.command("seed-db")
    def seed_db():
        if Users.query.filter_by(
            username = "admin"
        ).first():
            click.echo(" #️⃣ default admin is created")
            return
        admin = Users(
            username = 'admin',
            email = 'admin@powersys.local',
            password_hash = bcrypt.generate_password_hash("123456789").decode("utf-8"),
            role = UserRole.ADMIN,
            is_active = True,
            created_at= datetime.now(timezone.utc)
        )
        db.session.add(admin)
        db.session.commit()
        click.echo("😁 Dev Admin is created -> admin / 123456789")


auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods = ["POST"])
def register():
    data = request.get_json(silent =True) or {}
    username = data.get("username","").strip()
    email = data.get("email","").strip().lower()
    password = data.get("password", "")
    if not all([username, email, password]):
        return jsonify({
            'success': False,
            'message': 'Username and email password are required'
        }), 400
    if len(password) < 8:
        return jsonify({
            'success': False,
            'message': 'Password must be more than 8 characters'
        }), 400
    if Users.query.filter(
        (Users.username == username) | (Users.email == email) 
    ).first():
        return jsonify({
            'success': False, "message": "🆘 Username Already exists"
        }), 409
    user = Users(
        username = username,
        email = email,
        password_hash = bcrypt.generate_password_hash(password).decode("UTF-8"),
        role = UserRole.USER,
        created_at = datetime.now(timezone.utc)
    )
    db.session.add(user)
    db.session.commit()
    token = create_access_token(
        identity= str(user.id),
        additional_claims= {"role": user.role.value},
    )
    return jsonify({
        'success': True, "message":"Account Created", "token": token, "user": user.to_dict()
    }), 201

@auth_bp.route('/login', methods = ['POST'])
def login():
    data = request.get_json(silent= True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password","")
    if not all([email, password]):
        return jsonify({
            'success':False, 'message': "Email and password are required"
        }), 400
    user = Users.query.filter_by(email = email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({
            'success': False,'message': 'Invalid email or password'
        }), 401
    if not user.is_active:
        return jsonify({
            'success': True,
            'message': "Account deactivated, contact admin"
        }), 403
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()
    token = create_access_token(
        identity = str(user.id),
        additional_claims= {"role": user.role.value},
    )
    return jsonify({
        'success': False,
        'message': 'Login successful',
        "token": token,
        "user" : user.to_dict()
    }), 200

@auth_bp.route("/me", methods = ['GET'])
@jwt_required
def me():
    user = db.session.get(user, int(get_jwt_identity()))
    if not user:
        return jsonify({
            'success': False,
            'message': 'User not found'
        }), 404
    return jsonify({
        'success': True,
        "user": user.to_dict()
    }), 200

@auth_bp.route('/logout', methods = ['POST'])
def logout():
    return jsonify({
        "success": True,
        'message': "Logged out Successfully"
    }), 200

app = create_app()



if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port = 5000)
    