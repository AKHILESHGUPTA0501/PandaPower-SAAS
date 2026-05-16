from flask import Flask
from .auth_routes import auth_bp
from .user_routes import user_bp
from .network_routes import network_bp
from substation_routes import substation_bp
from .facility_routes import facility_bp
from .analysis_routes import analysis_bp
from .report_routes import report_bp
from .admin_routes import admin_bp

ALL_BLUEPRINTS = (
    auth_bp,
    user_bp,
    network_bp,
    substation_bp,
    facility_bp,
    analysis_bp,
    report_bp,
    admin_bp,
)

def register_blueprints(app :Flask) -> None:
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

__all__ = [
    "register_blueprints",
    "ALL_BLUEPRINTS",
    "auth_bp","user_bp", "network_bp","substation_bp","facility_bp",
    "analysis_bp","report_bp","admin_bp"
]
