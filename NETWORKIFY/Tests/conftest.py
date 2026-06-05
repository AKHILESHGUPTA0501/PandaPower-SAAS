"""
Shared pytest fixtures.

  - app                  : Flask app in TestingConfig (in-memory SQLite)
  - db                   : SQLAlchemy session, rolled back between tests
  - client               : Flask test client
  - admin_user / user    : fully created Users rows
  - admin_headers / auth_headers : pre-built Authorization headers
  - sample_network       : an IEEE 9-bus PowerNetwork ready to analyse
"""
import os
import pytest

# Force testing config before any app code imports settings
os.environ["FLASK_ENV"] = "testing"

from flask_jwt_extended import create_access_token

from main import create_app
from extension import db as _db, bcrypt
from Models import (
    Users, UserRole,
    PowerNetwork, NetworkStatus,
    Bus, Line, ExtGrid, Load,
    Substation, Facility, FacilityType, FacilitySize,
)


# ---------------------------------------------------------------------
#  App + DB
# ---------------------------------------------------------------------
@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        JWT_SECRET_KEY="test-secret",
        WTF_CSRF_ENABLED=False,
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(autouse=True)
def db_session(app):
    """Wrap each test in a savepoint-style cleanup."""
    with app.app_context():
        yield _db.session
        _db.session.rollback()
        # Wipe between tests so user IDs / uniqueness stay deterministic
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------
#  User factories
# ---------------------------------------------------------------------
def _make_user(username, email, password="Password1!", role=UserRole.USER,
               is_active=True):
    u = Users(
        username=username,
        email=email,
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        role=role,
        is_active=is_active,
        is_email_verified=True,
    )
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def user(app):
    return _make_user("testuser", "user@example.com")


@pytest.fixture
def engineer(app):
    return _make_user("engineer", "eng@example.com", role=UserRole.ENGINEER)


@pytest.fixture
def admin_user(app):
    return _make_user("admin", "admin@example.com", role=UserRole.ADMIN)


@pytest.fixture
def another_user(app):
    return _make_user("other", "other@example.com")


# ---------------------------------------------------------------------
#  Auth headers
# ---------------------------------------------------------------------
def _token_for(user: Users) -> str:
    return create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role.value, "username": user.username},
    )


@pytest.fixture
def auth_headers(user):
    return {"Authorization": f"Bearer {_token_for(user)}"}


@pytest.fixture
def engineer_headers(engineer):
    return {"Authorization": f"Bearer {_token_for(engineer)}"}


@pytest.fixture
def admin_headers(admin_user):
    return {"Authorization": f"Bearer {_token_for(admin_user)}"}


@pytest.fixture
def other_headers(another_user):
    return {"Authorization": f"Bearer {_token_for(another_user)}"}


# ---------------------------------------------------------------------
#  Domain factories
# ---------------------------------------------------------------------
@pytest.fixture
def empty_network(user):
    net = PowerNetwork(
        user_id=user.id,
        name="Empty Net",
        base_mva=100.0,
        freq_hz=50.0,
        status=NetworkStatus.DRAFT,
    )
    _db.session.add(net)
    _db.session.commit()
    return net


@pytest.fixture
def sample_network(user):
    """Tiny 2-bus radial network: ext_grid -> bus0 -- line -- bus1 -> load."""
    net = PowerNetwork(
        user_id=user.id, name="Sample 2-bus",
        base_mva=100.0, freq_hz=50.0, status=NetworkStatus.DRAFT,
    )
    _db.session.add(net); _db.session.flush()
    b0 = Bus(network_id=net.id, pp_index=0, name="HV", vn_kv=110.0)
    b1 = Bus(network_id=net.id, pp_index=1, name="LV", vn_kv=110.0)
    _db.session.add_all([b0, b1]); _db.session.flush()
    _db.session.add(ExtGrid(network_id=net.id, pp_index=0,
                            name="grid", bus_id=b0.id, vm_pu=1.02))
    _db.session.add(Line(
        network_id=net.id, pp_index=0, name="L1",
        from_bus_id=b0.id, to_bus_id=b1.id,
        length_km=10.0, r_ohm_per_km=0.1, x_ohm_per_km=0.2,
        c_nf_per_km=10.0, max_i_ka=1.0,
    ))
    _db.session.add(Load(
        network_id=net.id, pp_index=0, name="Ld",
        bus_id=b1.id, p_mw=50.0, q_mvar=20.0,
    ))
    _db.session.commit()
    return net


@pytest.fixture
def sample_substation(admin_user):
    sub = Substation(
        name="Test Sub",
        latitude=22.5726, longitude=88.3639,  # Kolkata
        primary_voltage_kv=132.0,
        secondary_voltage_kv=33.0,
        transformer_capacity_mva=100.0,
        current_loading_percent=40.0,
        s_sc_max_mva=2000.0,
        substation_type="distribution",
        is_active=True, is_public=True,
        uploaded_by_id=admin_user.id,
        data_source="manual",
        country="IN",
    )
    _db.session.add(sub); _db.session.commit()
    return sub


@pytest.fixture
def sample_facility(user):
    fac = Facility(
        user_id=user.id,
        name="ACME Factory",
        facility_type=FacilityType.FACTORY,
        size_class=FacilitySize.MEDIUM,
        latitude=22.58, longitude=88.36,    # ~1 km from sample_substation
        demand_mw=5.0,
        power_factor=0.9,
        required_voltage_kv=33.0,
        country="IN",
    )
    _db.session.add(fac); _db.session.commit()
    return fac
