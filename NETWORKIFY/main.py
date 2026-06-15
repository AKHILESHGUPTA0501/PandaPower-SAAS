"""
import eventlet
eventlet.monkey_patch()
import os 
import click
from datetime import datetime, timezone
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from config import config_map
from extension import db, jwt, socketio, bcrypt, init_extensions, celery


load_dotenv()

def create_app(config_name:str | None = None )-> Flask:
    app = Flask(__name__)
    env = config_name or os.getenv("FLASK_ENV", "development")
    app.config.from_object(config_map.get(env, config_map['development']))


    CORS(
        app,
        resources= {r"/api/*":{"origins": app.config.get("CORS_ORIGIN", "*")}},
        supports_credentials= True
    )
    init_extensions(app)
    from Utils import configure_logging, register_error_handlers, get_logger
    configure_logging(app)
    register_error_handlers(app)
    logger = get_logger(__name__)

    from Routes import register_blueprints
    register_blueprints(app)

    from Sockets import register_sockets
    register_sockets(socketio)
    @app.get('/api/health')
    def health():
        return {
            'status': 'ok',
            'env': env,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': app.config.get('APP_VERSION', 'dev'),
        }, 200
    @app.get('/')
    def root():
        return {
            'name': 'NETWORKIFY',
            'version': app.config.get('APP_VERSION', 'dev'),
            'docs': '/api/health'
        }, 200
    logger.info('NETWORKIFY -env=%s', env)
    return app


def register_cli(app: Flask)-> None:
    from Models import Users, UserRole
    @app.cli.command("create_db")
    def create_db():
        db.create_all()
        click.echo("✈️ Database Tables Created")
    @app.cli.command("drop-db")
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
        else:
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
        from Scripts.seed_plans import seed as seed_plans
        seed_plans(overwrite = False)
        from Scripts.seed_networks import seed as seed_networks, _DEFAULT_TEMPLATES
        seed_networks(_DEFAULT_TEMPLATES, owner_username= 'admin', overwrite= False)
        click.echo('✅ seed complete')


    @app.cli.command('routes-list')
    def routes_list():
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            methods = ','.join(sorted(rule.methods - {'HEAD', "OPTIONS'}"}))
            click.echo(f'  {methods:8s} {rule.rule}')


        



app = create_app()



if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = app.config.get('DEBUG', False)   
    socketio.run(app, debug=debug, host=host, port = port, allow_unsafe_werkzeug=debug)
"""
import eventlet
eventlet.monkey_patch()

import os
import click
from datetime import datetime, timezone

from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from config import config_map
from extension import db, jwt, socketio, bcrypt, init_extensions, celery


load_dotenv()

_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Templates")


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(
        __name__,
        static_folder="Templates",
        static_url_path="/Templates",
    )

    env = config_name or os.getenv("FLASK_ENV", "development")
    app.config.from_object(config_map.get(env, config_map["development"]))

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config.get("CORS_ORIGIN", "*")}},
        supports_credentials=True,
    )

    init_extensions(app)

    from Utils import configure_logging, register_error_handlers, get_logger
    configure_logging(app)
    register_error_handlers(app)
    logger = get_logger(__name__)

    from Routes import register_blueprints
    register_blueprints(app)

    from Sockets import register_sockets
    register_sockets(socketio)

    register_cli(app)

    @app.get("/api/health")
    def health():
        return {
            "status":    "ok",
            "env":       env,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version":   app.config.get("APP_VERSION", "dev"),
        }, 200

    @app.get("/api")
    def api_root():
        return {
            "name":    "NETWORKIFY API",
            "version": app.config.get("APP_VERSION", "dev"),
            "health":  "/api/health",
        }, 200

    @app.get("/")
    def index():
        return send_from_directory(_FRONTEND_DIR, "index.html")

    @app.get("/<path:path>")
    def spa_fallback(path):
        full = os.path.join(_FRONTEND_DIR, path)
        if os.path.isfile(full):
            return send_from_directory(_FRONTEND_DIR, path)
        if path.startswith("api/"):
            return {"success": False, "message": "Not found"}, 404
        return send_from_directory(_FRONTEND_DIR, "index.html")

    if app.config.get("DEBUG"):
        with app.app_context():
            db.create_all()

    logger.info("NETWORKIFY - env=%s", env)
    return app


def register_cli(app: Flask) -> None:
    from Models import Users, UserRole

    @app.cli.command("create-db")
    def create_db():
        db.create_all()
        click.echo("Database tables created")

    @app.cli.command("drop-db")
    @click.confirmation_option(prompt="This deletes all existing data. Are you sure?")
    def drop_db():
        db.drop_all()
        click.echo("All tables dropped")

    @app.cli.command("create-admin")
    @click.option("--username", prompt="Admin username")
    @click.option("--email", prompt="Admin email")
    @click.option("--password", prompt="Admin password",
                  hide_input=True, confirmation_prompt=True)
    def create_admin(username, email, password):
        if Users.query.filter(
            (Users.username == username) | (Users.email == email)
        ).first():
            click.echo("Username or email already exists")
            return
        admin = Users(
            username=username,
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            role=UserRole.ADMIN,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin '{username}' created")

    @app.cli.command("seed-db")
    def seed_db():
        if Users.query.filter_by(username="admin").first():
            click.echo("Default admin already exists")
        else:
            admin = Users(
                username="admin",
                email="admin@powersys.local",
                password_hash=bcrypt.generate_password_hash("123456789").decode("utf-8"),
                role=UserRole.ADMIN,
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(admin)
            db.session.commit()
            click.echo("Dev admin created -> admin / 123456789")
        from Scripts.seed_plans import seed as seed_plans
        seed_plans(overwrite=False)
        from Scripts.seed_networks import seed as seed_networks, _DEFAULT_TEMPLATES
        seed_networks(_DEFAULT_TEMPLATES, owner_username="admin", overwrite=False)
        click.echo("Seed complete")

    @app.cli.command("routes-list")
    def routes_list():
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
            click.echo(f"  {methods:8s} {rule.rule}")


app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    debug = app.config.get("DEBUG", False)
    socketio.run(app, debug=debug, host=host, port=port,
                 allow_unsafe_werkzeug=debug)
    