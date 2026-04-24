from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum as SAEnum
from datetime import datetime, timezone
import enum
import json
db = SQLAlchemy()

class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"

class NetworkStatus (enum.Enum):
    DRAFT = "draft"
    SAVED = "saved"
    ARCHIVED = "archived"

class AnalysisType(enum.Enum):
    LOAD_FLOW = "load_flow"
    SHORT_CIRCUIT = "short_circuit"
    CONTINGENCY = "contingency"
    OPTIMAL_POWER_FLOW = "optimal_power_flow"
class AnalysisStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class FaultType(enum.Enum):
    THREE_PHASE = "3ph"
    SINGLE_LINE_GROUND = "1ph"
    LINE_TO_LINE = "2ph"
    DOUBLE_LINE_GROUND = "2ph_ground"

class ElementType(enum.Enum):
    BUS = "bus"
    LINE = "line"
    TRANSFORMER = "transformer"
    LOAD = "load"
    GENERATOR = "generator"
    SHUNT = "shunt"
    EXT_GRID = "ext_grid"

class SeverityLevel(enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAl = "critical"

class Users(db.Model):
    __tablename__ = "users" 
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(50), unique = True, nullable = False)
    email = db.Column(db.String(120), unique =  True, nullable = False)
    password_hash = db.Column(db.String(256), nullable = False)
    role = db.Column(SAEnum(UserRole), default = UserRole.USER, nullable = False)
    is_active = db.Column(db.Boolean, default = True, nullable = False)
    created_at = db.Column(db.DateTime, default= lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable = True)
    networks = db.relationship("PowerNetwork", back_populates = "owner", cascade = "all, delete-orphan")
    analyses = db.relationship("AnalysisJob", back_populates = "user", cascade = "all, delete-orphan")
    def to_dict(self):
        return {
            "id":self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat()
        }
    def __repr__(self):
        return f"User {self.username}"
    
class PowerNetwork(db.Model):
    """
    Stores the complete pandapower network topology for one user project.
    The raw pandapower net is serialised to JSON and stored in `net_json`.
    Individual element tables (Bus, Line, etc.) mirror the net for
    querying and UI rendering without deserialising the whole net.
    """
    __tablename__ = "power_networks"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name        = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status      = db.Column(SAEnum(NetworkStatus), default=NetworkStatus.DRAFT, nullable=False)

    # Metadata
    base_mva    = db.Column(db.Float, default=100.0)       # system base MVA
    freq_hz     = db.Column(db.Float, default=50.0)        # 50 Hz (India) / 60 Hz
    is_template = db.Column(db.Boolean, default=False)     # IEEE preset flag
    template_name = db.Column(db.String(80), nullable=True)  # e.g. "IEEE 14-bus"

    # Serialised pandapower network (full fidelity backup)
    net_json    = db.Column(db.Text, nullable=True)        # pandapower.to_json()

    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    owner       = db.relationship("User", back_populates="networks")
    buses        = db.relationship("Bus",         back_populates="network", cascade="all, delete-orphan")
    lines        = db.relationship("Line",        back_populates="network", cascade="all, delete-orphan")
    transformers = db.relationship("Transformer", back_populates="network", cascade="all, delete-orphan")
    loads        = db.relationship("Load",        back_populates="network", cascade="all, delete-orphan")
    generators   = db.relationship("Generator",   back_populates="network", cascade="all, delete-orphan")
    ext_grids    = db.relationship("ExtGrid",     back_populates="network", cascade="all, delete-orphan")
    analyses     = db.relationship("AnalysisJob", back_populates="network", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":           self.id,
            "name":         self.name,
            "description":  self.description,
            "status":       self.status.value,
            "base_mva":     self.base_mva,
            "freq_hz":      self.freq_hz,
            "is_template":  self.is_template,
            "template_name":self.template_name,
            "bus_count":    len(self.buses),
            "line_count":   len(self.lines),
            "created_at":   self.created_at.isoformat(),
            "updated_at":   self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f"<PowerNetwork {self.name}>"
    


class Bus(db.Model):
    """
    Represents a pandapower bus node.
    vn_kv  : nominal voltage in kV
    bus_type: 'b' (PQ bus), 'n' (slack/reference), etc.
    """
    __tablename__ = "buses"

    id           = db.Column(db.Integer, primary_key=True)
    network_id   = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False)
    pp_index     = db.Column(db.Integer, nullable=False)   # pandapower internal index
    name         = db.Column(db.String(100), nullable=True)
    vn_kv        = db.Column(db.Float, nullable=False)     # nominal voltage (kV)
    bus_type     = db.Column(db.String(10), default="b")   # 'b', 'n', 'slack'
    in_service   = db.Column(db.Boolean, default=True)
    # Layout coords for topology visualisation
    geo_x        = db.Column(db.Float, nullable=True)
    geo_y        = db.Column(db.Float, nullable=True)
    zone         = db.Column(db.String(50), nullable=True)

    network      = db.relationship("PowerNetwork", back_populates="buses")

    def to_dict(self):
        return {
            "id": self.id, "pp_index": self.pp_index,
            "name": self.name, "vn_kv": self.vn_kv,
            "bus_type": self.bus_type, "in_service": self.in_service,
            "geo_x": self.geo_x, "geo_y": self.geo_y, "zone": self.zone,
        }

class Bus(db.Model):
    """
    Represents a pandapower bus node.
    vn_kv  : nominal voltage in kV
    bus_type: 'b' (PQ bus), 'n' (slack/reference), etc.
    """
    __tablename__ = "buses"

    id           = db.Column(db.Integer, primary_key=True)
    network_id   = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False)
    pp_index     = db.Column(db.Integer, nullable=False)   # pandapower internal index
    name         = db.Column(db.String(100), nullable=True)
    vn_kv        = db.Column(db.Float, nullable=False)     # nominal voltage (kV)
    bus_type     = db.Column(db.String(10), default="b")   # 'b', 'n', 'slack'
    in_service   = db.Column(db.Boolean, default=True)
    # Layout coords for topology visualisation
    geo_x        = db.Column(db.Float, nullable=True)
    geo_y        = db.Column(db.Float, nullable=True)
    zone         = db.Column(db.String(50), nullable=True)

    network      = db.relationship("PowerNetwork", back_populates="buses")

    def to_dict(self):
        return {
            "id": self.id, "pp_index": self.pp_index,
            "name": self.name, "vn_kv": self.vn_kv,
            "bus_type": self.bus_type, "in_service": self.in_service,
            "geo_x": self.geo_x, "geo_y": self.geo_y, "zone": self.zone,
        }



class Transformer(db.Model):
    """
    Two-winding transformer between HV and LV buses.
    """
    __tablename__ = "transformers"

    id           = db.Column(db.Integer, primary_key=True)
    network_id   = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False)
    pp_index     = db.Column(db.Integer, nullable=False)
    name         = db.Column(db.String(100), nullable=True)
    hv_bus_id    = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)
    lv_bus_id    = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)
    sn_mva       = db.Column(db.Float, nullable=False)       # rated power (MVA)
    vn_hv_kv     = db.Column(db.Float, nullable=False)       # HV nominal voltage
    vn_lv_kv     = db.Column(db.Float, nullable=False)       # LV nominal voltage
    vk_percent   = db.Column(db.Float, nullable=True)        # short-circuit voltage %
    vkr_percent  = db.Column(db.Float, nullable=True)        # resistive component %
    pfe_kw       = db.Column(db.Float, nullable=True)        # iron losses (kW)
    i0_percent   = db.Column(db.Float, nullable=True)        # no-load current %
    std_type     = db.Column(db.String(100), nullable=True)
    tap_pos      = db.Column(db.Integer, default=0)
    in_service   = db.Column(db.Boolean, default=True)

    network      = db.relationship("PowerNetwork", back_populates="transformers")
    hv_bus       = db.relationship("Bus", foreign_keys=[hv_bus_id])
    lv_bus       = db.relationship("Bus", foreign_keys=[lv_bus_id])

    def to_dict(self):
        return {
            "id": self.id, "pp_index": self.pp_index, "name": self.name,
            "hv_bus_id": self.hv_bus_id, "lv_bus_id": self.lv_bus_id,
            "sn_mva": self.sn_mva, "vn_hv_kv": self.vn_hv_kv,
            "vn_lv_kv": self.vn_lv_kv, "tap_pos": self.tap_pos,
            "in_service": self.in_service,
        }
    



class Load(db.Model):
    """
    Consumer load at a bus.  p_mw / q_mvar are the operating point values.
    """
    __tablename__ = "loads"

    id           = db.Column(db.Integer, primary_key=True)
    network_id   = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False)
    pp_index     = db.Column(db.Integer, nullable=False)
    name         = db.Column(db.String(100), nullable=True)
    bus_id       = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)
    p_mw         = db.Column(db.Float, nullable=False, default=0.0)   # active power (MW)
    q_mvar       = db.Column(db.Float, nullable=False, default=0.0)   # reactive power (MVAr)
    const_z_percent  = db.Column(db.Float, default=0.0)   # ZIP model: constant impedance %
    const_i_percent  = db.Column(db.Float, default=0.0)   # ZIP model: constant current %
    in_service   = db.Column(db.Boolean, default=True)

    network      = db.relationship("PowerNetwork", back_populates="loads")
    bus          = db.relationship("Bus", foreign_keys=[bus_id])

    def to_dict(self):
        return {
            "id": self.id, "pp_index": self.pp_index, "name": self.name,
            "bus_id": self.bus_id, "p_mw": self.p_mw,
            "q_mvar": self.q_mvar, "in_service": self.in_service,
        }



class Generator(db.Model):
    """
    Synchronous generator (PV bus source).
    vm_pu   : voltage magnitude set-point (per unit)
    p_mw    : active power injection
    """
    __tablename__ = "generators"

    id           = db.Column(db.Integer, primary_key=True)
    network_id   = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False)
    pp_index     = db.Column(db.Integer, nullable=False)
    name         = db.Column(db.String(100), nullable=True)
    bus_id       = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)
    p_mw         = db.Column(db.Float, nullable=False, default=0.0)
    vm_pu        = db.Column(db.Float, nullable=False, default=1.0)   # voltage set-point
    sn_mva       = db.Column(db.Float, nullable=True)                 # rated MVA
    min_q_mvar   = db.Column(db.Float, nullable=True)
    max_q_mvar   = db.Column(db.Float, nullable=True)
    min_p_mw     = db.Column(db.Float, nullable=True)
    max_p_mw     = db.Column(db.Float, nullable=True)
    # OPF cost function  (quadratic: cost = cp2*p² + cp1*p + cp0)
    cp2_eur_per_mw2 = db.Column(db.Float, default=0.0)
    cp1_eur_per_mw  = db.Column(db.Float, default=0.0)
    cp0_eur        = db.Column(db.Float, default=0.0)
    in_service   = db.Column(db.Boolean, default=True)

    network      = db.relationship("PowerNetwork", back_populates="generators")
    bus          = db.relationship("Bus", foreign_keys=[bus_id])

    def to_dict(self):
        return {
            "id": self.id, "pp_index": self.pp_index, "name": self.name,
            "bus_id": self.bus_id, "p_mw": self.p_mw, "vm_pu": self.vm_pu,
            "sn_mva": self.sn_mva, "in_service": self.in_service,
        }





class ExtGrid(db.Model):
    """
    External grid connection (slack bus reference).
    Represents the point of common coupling with the upstream grid.
    """
    __tablename__ = "ext_grids"

    id           = db.Column(db.Integer, primary_key=True)
    network_id   = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False)
    pp_index     = db.Column(db.Integer, nullable=False)
    name         = db.Column(db.String(100), nullable=True)
    bus_id       = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)
    vm_pu        = db.Column(db.Float, default=1.0)
    va_degree    = db.Column(db.Float, default=0.0)       # voltage angle (degrees)
    s_sc_max_mva = db.Column(db.Float, nullable=True)     # max short-circuit MVA
    s_sc_min_mva = db.Column(db.Float, nullable=True)
    in_service   = db.Column(db.Boolean, default=True)

    network      = db.relationship("PowerNetwork", back_populates="ext_grids")
    bus          = db.relationship("Bus", foreign_keys=[bus_id])

class AnalysisJob(db.Model):
    """
    Tracks every analysis run (load flow, SC, contingency, OPF).
    Celery task_id links to the async worker.
    results_json stores the full pandapower result tables as JSON.
    """
    __tablename__ = "analysis_jobs"

    id            = db.Column(db.Integer, primary_key=True)
    network_id    = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    analysis_type = db.Column(SAEnum(AnalysisType), nullable=False)
    status        = db.Column(SAEnum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False)
    task_id       = db.Column(db.String(36), nullable=True)   # Celery UUID
    # Configuration passed in by user (e.g. algorithm choice, fault bus)
    config_json   = db.Column(db.Text, nullable=True)
    # Full results from pandapower (res_bus, res_line, etc.)
    results_json  = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    # Runtime
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at    = db.Column(db.DateTime, nullable=True)
    completed_at  = db.Column(db.DateTime, nullable=True)
    duration_sec  = db.Column(db.Float, nullable=True)

    network       = db.relationship("PowerNetwork", back_populates="analyses")
    user          = db.relationship("User", back_populates="analyses")
    violations    = db.relationship("Violation", back_populates="job", cascade="all, delete-orphan")
    fault_results = db.relationship("FaultResult", back_populates="job", cascade="all, delete-orphan")

    @property
    def config(self):
        return json.loads(self.config_json) if self.config_json else {}

    @property
    def results(self):
        return json.loads(self.results_json) if self.results_json else {}

    def to_dict(self):
        return {
            "id":            self.id,
            "network_id":    self.network_id,
            "analysis_type": self.analysis_type.value,
            "status":        self.status.value,
            "task_id":       self.task_id,
            "config":        self.config,
            "error_message": self.error_message,
            "created_at":    self.created_at.isoformat(),
            "completed_at":  self.completed_at.isoformat() if self.completed_at else None,
            "duration_sec":  self.duration_sec,
        }

    def __repr__(self):
        return f"<AnalysisJob {self.analysis_type.value} [{self.status.value}]>"

class Violation(db.Model):
    """
    Individual constraint violation detected in an analysis run.
    Examples: over-voltage, under-voltage, thermal overload.
    """
    __tablename__ = "violations"

    id              = db.Column(db.Integer, primary_key=True)
    job_id          = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"), nullable=False)
    element_type    = db.Column(SAEnum(ElementType), nullable=False)
    element_pp_index= db.Column(db.Integer, nullable=False)   # pandapower index of the element
    element_name    = db.Column(db.String(100), nullable=True)
    violation_type  = db.Column(db.String(80), nullable=False) # e.g. "overvoltage", "thermal_overload"
    severity        = db.Column(SAEnum(SeverityLevel), nullable=False)
    value           = db.Column(db.Float, nullable=True)       # actual measured value
    limit           = db.Column(db.Float, nullable=True)       # allowed limit
    unit            = db.Column(db.String(20), nullable=True)  # "pu", "kA", "%", etc.
    message         = db.Column(db.Text, nullable=True)

    job             = db.relationship("AnalysisJob", back_populates="violations")

    def to_dict(self):
        return {
            "id":             self.id,
            "element_type":   self.element_type.value,
            "element_index":  self.element_pp_index,
            "element_name":   self.element_name,
            "violation_type": self.violation_type,
            "severity":       self.severity.value,
            "value":          self.value,
            "limit":          self.limit,
            "unit":           self.unit,
            "message":        self.message,
        }

class FaultResult(db.Model):
    """
    Detailed short-circuit / fault analysis result per bus.
    Stores Ikss (initial symmetrical short-circuit current) and
    other IEC 60909 quantities computed by pandapower.shortcircuit.
    """
    __tablename__ = "fault_results"

    id              = db.Column(db.Integer, primary_key=True)
    job_id          = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"), nullable=False)
    fault_type      = db.Column(SAEnum(FaultType), nullable=False)
    fault_bus_id    = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=True)
    # IEC 60909 quantities
    ikss_ka         = db.Column(db.Float, nullable=True)   # initial SC current (kA)
    skss_mw         = db.Column(db.Float, nullable=True)   # initial SC power (MW)
    ip_ka           = db.Column(db.Float, nullable=True)   # peak SC current
    ith_ka          = db.Column(db.Float, nullable=True)   # thermal equivalent SC current
    # Bus voltage during fault
    vm_pu           = db.Column(db.Float, nullable=True)
    # Full result row as JSON (for detailed display)
    raw_json        = db.Column(db.Text, nullable=True)

    job             = db.relationship("AnalysisJob", back_populates="fault_results")
    fault_bus       = db.relationship("Bus", foreign_keys=[fault_bus_id])

    def to_dict(self):
        return {
            "id":           self.id,
            "fault_type":   self.fault_type.value,
            "fault_bus_id": self.fault_bus_id,
            "ikss_ka":      self.ikss_ka,
            "skss_mw":      self.skss_mw,
            "ip_ka":        self.ip_ka,
            "vm_pu":        self.vm_pu,
        }

class ContingencyResult(db.Model):
    """
    One row per (contingency, element) outcome in an N-1 analysis.
    Records whether removing a line/transformer caused any violations.
    """
    __tablename__ = "contingency_results"

    id                  = db.Column(db.Integer, primary_key=True)
    job_id              = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"), nullable=False)
    outaged_element_type= db.Column(SAEnum(ElementType), nullable=False)
    outaged_pp_index    = db.Column(db.Integer, nullable=False)
    outaged_name        = db.Column(db.String(100), nullable=True)
    converged           = db.Column(db.Boolean, nullable=False, default=True)
    max_loading_percent = db.Column(db.Float, nullable=True)   # worst line loading %
    min_vm_pu           = db.Column(db.Float, nullable=True)   # worst bus voltage
    max_vm_pu           = db.Column(db.Float, nullable=True)
    violation_count     = db.Column(db.Integer, default=0)
    risk_score          = db.Column(db.Float, nullable=True)   # composite severity score
    results_json        = db.Column(db.Text, nullable=True)    # full snapshot

    job                 = db.relationship("AnalysisJob")

    def to_dict(self):
        return {
            "id":                   self.id,
            "outaged_element_type": self.outaged_element_type.value,
            "outaged_pp_index":     self.outaged_pp_index,
            "outaged_name":         self.outaged_name,
            "converged":            self.converged,
            "max_loading_percent":  self.max_loading_percent,
            "min_vm_pu":            self.min_vm_pu,
            "max_vm_pu":            self.max_vm_pu,
            "violation_count":      self.violation_count,
            "risk_score":           self.risk_score,
        }


class Report(db.Model):
    """
    Generated PDF/Excel report linked to one analysis job.
    file_path is relative to the UPLOAD_FOLDER.
    """
    __tablename__ = "reports"

    id          = db.Column(db.Integer, primary_key=True)
    job_id      = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title       = db.Column(db.String(200), nullable=False)
    format      = db.Column(db.String(10), nullable=False)   # "pdf" | "xlsx"
    file_path   = db.Column(db.String(300), nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    job         = db.relationship("AnalysisJob")
    user        = db.relationship("User")

    def to_dict(self):
        return {
            "id":         self.id,
            "job_id":     self.job_id,
            "title":      self.title,
            "format":     self.format,
            "created_at": self.created_at.isoformat(),
        }