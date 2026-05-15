"""
Power network topology models.

Mirrors the pandapower element tables (net.bus, net.line, net.trafo, etc.)
so the topology can be queried by SQL and rendered in the UI without
deserialising the full pandapower net every time.

The authoritative pandapower network is also stored as JSON in
PowerNetwork.net_json (from pandapower.to_json()) for full fidelity.
"""

from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum

from extension import db
from .models import NetworkStatus


# ---------------------------------------------------------------------------
# PowerNetwork (project container)
# ---------------------------------------------------------------------------
class PowerNetwork(db.Model):
    """
    A complete pandapower network owned by one user.
    Each PowerNetwork is one project / study case.
    """
    __tablename__ = "power_networks"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    project_id  = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)

    name        = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status      = db.Column(SAEnum(NetworkStatus), default=NetworkStatus.DRAFT, nullable=False)

    # System metadata
    base_mva      = db.Column(db.Float, default=100.0)   # system base MVA
    freq_hz       = db.Column(db.Float, default=50.0)    # 50 Hz (India) / 60 Hz (US)
    is_template   = db.Column(db.Boolean, default=False) # IEEE preset flag
    template_name = db.Column(db.String(80), nullable=True)

    # Serialised pandapower network (full fidelity backup)
    net_json    = db.Column(db.Text, nullable=True)      # pandapower.to_json()

    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner        = db.relationship("Users", back_populates="networks")
    project      = db.relationship("Project", back_populates="networks")
    buses        = db.relationship("Bus",         back_populates="network", cascade="all, delete-orphan")
    lines        = db.relationship("Line",        back_populates="network", cascade="all, delete-orphan")
    transformers = db.relationship("Transformer", back_populates="network", cascade="all, delete-orphan")
    loads        = db.relationship("Load",        back_populates="network", cascade="all, delete-orphan")
    generators   = db.relationship("Generator",   back_populates="network", cascade="all, delete-orphan")
    ext_grids    = db.relationship("ExtGrid",     back_populates="network", cascade="all, delete-orphan")
    shunts       = db.relationship("Shunt",       back_populates="network", cascade="all, delete-orphan")
    switches     = db.relationship("Switch",      back_populates="network", cascade="all, delete-orphan")
    analyses     = db.relationship("AnalysisJob", back_populates="network", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "user_id":       self.user_id,
            "project_id":    self.project_id,
            "name":          self.name,
            "description":   self.description,
            "status":        self.status.value,
            "base_mva":      self.base_mva,
            "freq_hz":       self.freq_hz,
            "is_template":   self.is_template,
            "template_name": self.template_name,
            "bus_count":     len(self.buses),
            "line_count":    len(self.lines),
            "trafo_count":   len(self.transformers),
            "load_count":    len(self.loads),
            "gen_count":     len(self.generators),
            "created_at":    self.created_at.isoformat() if self.created_at else None,
            "updated_at":    self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<PowerNetwork {self.name} ({self.status.value})>"


# ---------------------------------------------------------------------------
# Bus
# ---------------------------------------------------------------------------
class Bus(db.Model):
    """
    Pandapower bus node.
    """
    __tablename__ = "buses"

    id         = db.Column(db.Integer, primary_key=True)
    network_id = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False, index=True)
    pp_index   = db.Column(db.Integer, nullable=False)
    name       = db.Column(db.String(100), nullable=True)
    vn_kv      = db.Column(db.Float, nullable=False)
    bus_type   = db.Column(db.String(10), default="b")
    in_service = db.Column(db.Boolean, default=True)

    geo_x      = db.Column(db.Float, nullable=True)
    geo_y      = db.Column(db.Float, nullable=True)
    zone       = db.Column(db.String(50), nullable=True)

    min_vm_pu  = db.Column(db.Float, default=0.95)
    max_vm_pu  = db.Column(db.Float, default=1.05)

    network    = db.relationship("PowerNetwork", back_populates="buses")

    __table_args__ = (
        db.UniqueConstraint("network_id", "pp_index", name="uq_bus_network_ppindex"),
    )

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "pp_index":   self.pp_index,
            "name":       self.name,
            "vn_kv":      self.vn_kv,
            "bus_type":   self.bus_type,
            "in_service": self.in_service,
            "geo_x":      self.geo_x,
            "geo_y":      self.geo_y,
            "zone":       self.zone,
            "min_vm_pu":  self.min_vm_pu,
            "max_vm_pu":  self.max_vm_pu,
        }

    def __repr__(self):
        return f"<Bus {self.name or self.pp_index} @ {self.vn_kv}kV>"


# ---------------------------------------------------------------------------
# Line
# ---------------------------------------------------------------------------
class Line(db.Model):
    """
    Transmission / distribution line between two buses.
    """
    __tablename__ = "lines"

    id          = db.Column(db.Integer, primary_key=True)
    network_id  = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False, index=True)
    pp_index    = db.Column(db.Integer, nullable=False)
    name        = db.Column(db.String(100), nullable=True)
    from_bus_id = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)
    to_bus_id   = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)

    length_km   = db.Column(db.Float, nullable=False, default=1.0)
    std_type    = db.Column(db.String(100), nullable=True)

    r_ohm_per_km = db.Column(db.Float, nullable=True)
    x_ohm_per_km = db.Column(db.Float, nullable=True)
    c_nf_per_km  = db.Column(db.Float, nullable=True)
    g_us_per_km  = db.Column(db.Float, nullable=True)

    max_i_ka    = db.Column(db.Float, nullable=True)
    parallel    = db.Column(db.Integer, default=1)
    df          = db.Column(db.Float, default=1.0)
    in_service  = db.Column(db.Boolean, default=True)

    network     = db.relationship("PowerNetwork", back_populates="lines")
    from_bus    = db.relationship("Bus", foreign_keys=[from_bus_id])
    to_bus      = db.relationship("Bus", foreign_keys=[to_bus_id])

    __table_args__ = (
        db.UniqueConstraint("network_id", "pp_index", name="uq_line_network_ppindex"),
    )

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "pp_index":     self.pp_index,
            "name":         self.name,
            "from_bus_id":  self.from_bus_id,
            "to_bus_id":    self.to_bus_id,
            "length_km":    self.length_km,
            "std_type":     self.std_type,
            "r_ohm_per_km": self.r_ohm_per_km,
            "x_ohm_per_km": self.x_ohm_per_km,
            "max_i_ka":     self.max_i_ka,
            "parallel":     self.parallel,
            "in_service":   self.in_service,
        }


# ---------------------------------------------------------------------------
# Transformer
# ---------------------------------------------------------------------------
class Transformer(db.Model):
    """Two-winding transformer between HV and LV buses."""
    __tablename__ = "transformers"

    id          = db.Column(db.Integer, primary_key=True)
    network_id  = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False, index=True)
    pp_index    = db.Column(db.Integer, nullable=False)
    name        = db.Column(db.String(100), nullable=True)
    hv_bus_id   = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)
    lv_bus_id   = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)

    sn_mva      = db.Column(db.Float, nullable=False)
    vn_hv_kv    = db.Column(db.Float, nullable=False)
    vn_lv_kv    = db.Column(db.Float, nullable=False)
    vk_percent  = db.Column(db.Float, nullable=True)
    vkr_percent = db.Column(db.Float, nullable=True)
    pfe_kw      = db.Column(db.Float, nullable=True)
    i0_percent  = db.Column(db.Float, nullable=True)

    std_type    = db.Column(db.String(100), nullable=True)

    tap_pos          = db.Column(db.Integer, default=0)
    tap_min          = db.Column(db.Integer, nullable=True)
    tap_max          = db.Column(db.Integer, nullable=True)
    tap_step_percent = db.Column(db.Float, nullable=True)
    tap_side         = db.Column(db.String(2), nullable=True)  # 'hv' or 'lv'

    parallel    = db.Column(db.Integer, default=1)
    in_service  = db.Column(db.Boolean, default=True)

    network     = db.relationship("PowerNetwork", back_populates="transformers")
    hv_bus      = db.relationship("Bus", foreign_keys=[hv_bus_id])
    lv_bus      = db.relationship("Bus", foreign_keys=[lv_bus_id])

    __table_args__ = (
        db.UniqueConstraint("network_id", "pp_index", name="uq_trafo_network_ppindex"),
    )

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "pp_index":   self.pp_index,
            "name":       self.name,
            "hv_bus_id":  self.hv_bus_id,
            "lv_bus_id":  self.lv_bus_id,
            "sn_mva":     self.sn_mva,
            "vn_hv_kv":   self.vn_hv_kv,
            "vn_lv_kv":   self.vn_lv_kv,
            "vk_percent": self.vk_percent,
            "tap_pos":    self.tap_pos,
            "in_service": self.in_service,
        }


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
class Load(db.Model):
    """Consumer load at a bus."""
    __tablename__ = "loads"

    id          = db.Column(db.Integer, primary_key=True)
    network_id  = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False, index=True)
    pp_index    = db.Column(db.Integer, nullable=False)
    name        = db.Column(db.String(100), nullable=True)
    bus_id      = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)

    p_mw        = db.Column(db.Float, nullable=False, default=0.0)
    q_mvar      = db.Column(db.Float, nullable=False, default=0.0)
    sn_mva      = db.Column(db.Float, nullable=True)
    scaling     = db.Column(db.Float, default=1.0)

    const_z_percent = db.Column(db.Float, default=0.0)
    const_i_percent = db.Column(db.Float, default=0.0)

    load_type   = db.Column(db.String(50), nullable=True)
    in_service  = db.Column(db.Boolean, default=True)

    network     = db.relationship("PowerNetwork", back_populates="loads")
    bus         = db.relationship("Bus", foreign_keys=[bus_id])

    __table_args__ = (
        db.UniqueConstraint("network_id", "pp_index", name="uq_load_network_ppindex"),
    )

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "pp_index":   self.pp_index,
            "name":       self.name,
            "bus_id":     self.bus_id,
            "p_mw":       self.p_mw,
            "q_mvar":     self.q_mvar,
            "scaling":    self.scaling,
            "load_type":  self.load_type,
            "in_service": self.in_service,
        }


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------
class Generator(db.Model):
    """Synchronous generator (PV bus source)."""
    __tablename__ = "generators"

    id          = db.Column(db.Integer, primary_key=True)
    network_id  = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False, index=True)
    pp_index    = db.Column(db.Integer, nullable=False)
    name        = db.Column(db.String(100), nullable=True)
    bus_id      = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)

    p_mw        = db.Column(db.Float, nullable=False, default=0.0)
    vm_pu       = db.Column(db.Float, nullable=False, default=1.0)
    sn_mva      = db.Column(db.Float, nullable=True)

    min_q_mvar  = db.Column(db.Float, nullable=True)
    max_q_mvar  = db.Column(db.Float, nullable=True)
    min_p_mw    = db.Column(db.Float, nullable=True)
    max_p_mw    = db.Column(db.Float, nullable=True)

    # OPF quadratic cost: cost = cp2*p² + cp1*p + cp0
    cp2_cost    = db.Column(db.Float, default=0.0)
    cp1_cost    = db.Column(db.Float, default=0.0)
    cp0_cost    = db.Column(db.Float, default=0.0)

    gen_type    = db.Column(db.String(50), nullable=True)  # 'thermal', 'hydro', 'solar', 'wind'
    slack       = db.Column(db.Boolean, default=False)
    in_service  = db.Column(db.Boolean, default=True)

    network     = db.relationship("PowerNetwork", back_populates="generators")
    bus         = db.relationship("Bus", foreign_keys=[bus_id])

    __table_args__ = (
        db.UniqueConstraint("network_id", "pp_index", name="uq_gen_network_ppindex"),
    )

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "pp_index":   self.pp_index,
            "name":       self.name,
            "bus_id":     self.bus_id,
            "p_mw":       self.p_mw,
            "vm_pu":      self.vm_pu,
            "sn_mva":     self.sn_mva,
            "gen_type":   self.gen_type,
            "slack":      self.slack,
            "in_service": self.in_service,
        }


# ---------------------------------------------------------------------------
# ExtGrid
# ---------------------------------------------------------------------------
class ExtGrid(db.Model):
    """External grid connection (slack reference)."""
    __tablename__ = "ext_grids"

    id          = db.Column(db.Integer, primary_key=True)
    network_id  = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False, index=True)
    pp_index    = db.Column(db.Integer, nullable=False)
    name        = db.Column(db.String(100), nullable=True)
    bus_id      = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)

    vm_pu        = db.Column(db.Float, default=1.0)
    va_degree    = db.Column(db.Float, default=0.0)
    s_sc_max_mva = db.Column(db.Float, nullable=True)
    s_sc_min_mva = db.Column(db.Float, nullable=True)
    rx_max       = db.Column(db.Float, nullable=True)
    rx_min       = db.Column(db.Float, nullable=True)

    in_service  = db.Column(db.Boolean, default=True)

    network     = db.relationship("PowerNetwork", back_populates="ext_grids")
    bus         = db.relationship("Bus", foreign_keys=[bus_id])

    __table_args__ = (
        db.UniqueConstraint("network_id", "pp_index", name="uq_extgrid_network_ppindex"),
    )

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "pp_index":     self.pp_index,
            "name":         self.name,
            "bus_id":       self.bus_id,
            "vm_pu":        self.vm_pu,
            "va_degree":    self.va_degree,
            "s_sc_max_mva": self.s_sc_max_mva,
            "in_service":   self.in_service,
        }


# ---------------------------------------------------------------------------
# Shunt
# ---------------------------------------------------------------------------
class Shunt(db.Model):
    """Shunt element for reactive compensation (capacitor banks, reactors)."""
    __tablename__ = "shunts"

    id          = db.Column(db.Integer, primary_key=True)
    network_id  = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False, index=True)
    pp_index    = db.Column(db.Integer, nullable=False)
    name        = db.Column(db.String(100), nullable=True)
    bus_id      = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)

    p_mw        = db.Column(db.Float, default=0.0)
    q_mvar      = db.Column(db.Float, default=0.0)   # +ve = reactor, -ve = capacitor
    vn_kv       = db.Column(db.Float, nullable=True)
    step        = db.Column(db.Integer, default=1)
    max_step    = db.Column(db.Integer, default=1)
    in_service  = db.Column(db.Boolean, default=True)

    network     = db.relationship("PowerNetwork", back_populates="shunts")
    bus         = db.relationship("Bus", foreign_keys=[bus_id])

    __table_args__ = (
        db.UniqueConstraint("network_id", "pp_index", name="uq_shunt_network_ppindex"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id, "pp_index": self.pp_index, "name": self.name,
            "bus_id": self.bus_id, "p_mw": self.p_mw, "q_mvar": self.q_mvar,
            "step": self.step, "in_service": self.in_service,
        }


# ---------------------------------------------------------------------------
# Switch
# ---------------------------------------------------------------------------
class Switch(db.Model):
    """
    Switch / circuit breaker between a bus and another element.
    element_type: 'b' (bus-bus), 'l' (line), 't' (transformer), 't3' (3W trafo)
    """
    __tablename__ = "switches"

    id            = db.Column(db.Integer, primary_key=True)
    network_id    = db.Column(db.Integer, db.ForeignKey("power_networks.id"), nullable=False, index=True)
    pp_index      = db.Column(db.Integer, nullable=False)
    name          = db.Column(db.String(100), nullable=True)
    bus_id        = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=False)
    element_type  = db.Column(db.String(4), nullable=False)
    element_pp_index = db.Column(db.Integer, nullable=False)
    closed        = db.Column(db.Boolean, default=True)
    switch_type   = db.Column(db.String(20), nullable=True)  # 'CB', 'LS', 'LBS', 'DS'
    in_service    = db.Column(db.Boolean, default=True)

    network       = db.relationship("PowerNetwork", back_populates="switches")
    bus           = db.relationship("Bus", foreign_keys=[bus_id])

    __table_args__ = (
        db.UniqueConstraint("network_id", "pp_index", name="uq_switch_network_ppindex"),
    )

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "pp_index":         self.pp_index,
            "name":             self.name,
            "bus_id":           self.bus_id,
            "element_type":     self.element_type,
            "element_pp_index": self.element_pp_index,
            "closed":           self.closed,
            "switch_type":      self.switch_type,
            "in_service":       self.in_service,
        }
