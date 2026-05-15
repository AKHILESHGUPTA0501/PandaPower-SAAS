"""
Substation database models.

Stores real-world substation data — populated from OpenStreetMap Overpass
(power=substation tag), uploaded utility CSV, or manual entry.

These are the substations consultant engineers query when checking whether
a proposed facility can be powered from the nearest grid connection.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum, Index

from extension import db


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class SubstationStatus(enum.Enum):
    OPERATIONAL = "operational"
    UNDER_CONSTRUCTION = "under_construction"
    PLANNED = "planned"
    DECOMMISSIONED = "decommissioned"


class SubstationType(enum.Enum):
    TRANSMISSION = "transmission"     # 220 kV+
    SUB_TRANSMISSION = "sub_transmission"  # 66-132 kV
    DISTRIBUTION = "distribution"     # 11-33 kV
    INDUSTRIAL = "industrial"         # private / captive
    SWITCHING = "switching"           # no transformation
    DATA_CENTER = "data_center"       # dedicated DC substation


# ---------------------------------------------------------------------------
# Substation
# ---------------------------------------------------------------------------
class Substation(db.Model):
    """
    A physical substation that may be a candidate for facility connection.
    Either platform-wide (uploaded by admin) or project-scoped (user upload).
    """
    __tablename__ = "substations"

    id              = db.Column(db.Integer, primary_key=True)
    # If project_id is set, this substation is private to that project.
    # If null, it's part of the public/admin-managed substation database.
    project_id      = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    uploaded_by_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Identification
    name            = db.Column(db.String(150), nullable=False, index=True)
    code            = db.Column(db.String(50), nullable=True, index=True)   # utility code
    operator        = db.Column(db.String(120), nullable=True)              # e.g. "WBSEDCL", "PGCIL"
    osm_id          = db.Column(db.BigInteger, nullable=True, unique=True)  # OpenStreetMap ref

    # Location
    latitude        = db.Column(db.Float, nullable=False)
    longitude       = db.Column(db.Float, nullable=False)
    address         = db.Column(db.String(300), nullable=True)
    city            = db.Column(db.String(100), nullable=True)
    state           = db.Column(db.String(100), nullable=True)
    country         = db.Column(db.String(60), nullable=True)
    pincode         = db.Column(db.String(20), nullable=True)

    # Electrical characteristics
    substation_type = db.Column(SAEnum(SubstationType), nullable=False,
                                default=SubstationType.DISTRIBUTION)
    primary_voltage_kv   = db.Column(db.Float, nullable=False)   # HV side
    secondary_voltage_kv = db.Column(db.Float, nullable=True)    # LV side (null for switching)
    tertiary_voltage_kv  = db.Column(db.Float, nullable=True)    # if 3-winding

    # Capacity
    total_capacity_mva   = db.Column(db.Float, nullable=False)
    available_capacity_mva = db.Column(db.Float, nullable=True)  # remaining headroom
    transformer_count    = db.Column(db.Integer, default=1)

    # Current operating state (snapshot)
    current_loading_percent = db.Column(db.Float, nullable=True)   # 0-100+
    peak_loading_percent    = db.Column(db.Float, nullable=True)
    load_factor             = db.Column(db.Float, nullable=True)   # avg/peak

    # Short-circuit strength (for fault studies)
    sc_capacity_mva    = db.Column(db.Float, nullable=True)
    sc_current_ka      = db.Column(db.Float, nullable=True)

    # Status & metadata
    status          = db.Column(SAEnum(SubstationStatus),
                                default=SubstationStatus.OPERATIONAL, nullable=False)
    commissioned_year = db.Column(db.Integer, nullable=True)
    notes           = db.Column(db.Text, nullable=True)
    data_source     = db.Column(db.String(60), nullable=True)   # 'osm', 'manual', 'utility_csv'

    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    project         = db.relationship("Project", back_populates="substations")
    uploaded_by     = db.relationship("Users", foreign_keys=[uploaded_by_id])
    feeders         = db.relationship(
        "SubstationFeeder", back_populates="substation", cascade="all, delete-orphan"
    )
    feasibility_checks = db.relationship(
        "FeasibilityCheck", back_populates="substation"
    )

    __table_args__ = (
        # Composite index for geo proximity queries (PostGIS preferred in prod)
        Index("ix_substation_lat_lng", "latitude", "longitude"),
        Index("ix_substation_state_city", "state", "city"),
    )

    @property
    def utilization_percent(self) -> float | None:
        """Current load / total capacity * 100."""
        if self.current_loading_percent is not None:
            return self.current_loading_percent
        if self.total_capacity_mva and self.available_capacity_mva is not None:
            used = self.total_capacity_mva - self.available_capacity_mva
            return (used / self.total_capacity_mva) * 100.0
        return None

    @property
    def headroom_mva(self) -> float | None:
        """Available MVA capacity for new connections."""
        if self.available_capacity_mva is not None:
            return self.available_capacity_mva
        if self.current_loading_percent is not None and self.total_capacity_mva:
            return self.total_capacity_mva * (1 - self.current_loading_percent / 100.0)
        return None

    def to_dict(self) -> dict:
        return {
            "id":                     self.id,
            "name":                   self.name,
            "code":                   self.code,
            "operator":               self.operator,
            "latitude":               self.latitude,
            "longitude":              self.longitude,
            "city":                   self.city,
            "state":                  self.state,
            "country":                self.country,
            "substation_type":        self.substation_type.value,
            "primary_voltage_kv":     self.primary_voltage_kv,
            "secondary_voltage_kv":   self.secondary_voltage_kv,
            "total_capacity_mva":     self.total_capacity_mva,
            "available_capacity_mva": self.available_capacity_mva,
            "headroom_mva":           self.headroom_mva,
            "utilization_percent":    self.utilization_percent,
            "sc_capacity_mva":        self.sc_capacity_mva,
            "status":                 self.status.value,
            "data_source":            self.data_source,
            "created_at":             self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Substation {self.name} {self.primary_voltage_kv}kV>"


# ---------------------------------------------------------------------------
# Substation Feeder
# ---------------------------------------------------------------------------
class SubstationFeeder(db.Model):
    """
    Outgoing feeder (distribution circuit) from a substation.
    Used to model loading and identify which feeder a facility would tap into.
    """
    __tablename__ = "substation_feeders"

    id              = db.Column(db.Integer, primary_key=True)
    substation_id   = db.Column(db.Integer, db.ForeignKey("substations.id"), nullable=False, index=True)
    name            = db.Column(db.String(120), nullable=False)
    feeder_code     = db.Column(db.String(50), nullable=True)

    voltage_kv      = db.Column(db.Float, nullable=False)
    rated_current_a = db.Column(db.Float, nullable=True)
    rated_mva       = db.Column(db.Float, nullable=True)
    current_loading_percent = db.Column(db.Float, nullable=True)

    conductor_type  = db.Column(db.String(60), nullable=True)   # 'ACSR Dog', 'XLPE 240', etc.
    length_km       = db.Column(db.Float, nullable=True)
    is_underground  = db.Column(db.Boolean, default=False)

    serves_area     = db.Column(db.String(200), nullable=True)
    in_service      = db.Column(db.Boolean, default=True)

    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    substation      = db.relationship("Substation", back_populates="feeders")

    def to_dict(self) -> dict:
        return {
            "id":                      self.id,
            "substation_id":           self.substation_id,
            "name":                    self.name,
            "feeder_code":             self.feeder_code,
            "voltage_kv":              self.voltage_kv,
            "rated_mva":               self.rated_mva,
            "current_loading_percent": self.current_loading_percent,
            "conductor_type":          self.conductor_type,
            "length_km":               self.length_km,
            "is_underground":          self.is_underground,
            "in_service":              self.in_service,
        }


# ---------------------------------------------------------------------------
# Transmission Line (between substations)
# ---------------------------------------------------------------------------
class TransmissionLine(db.Model):
    """
    Inter-substation transmission line.
    Used to model the wider grid around a candidate connection point.
    """
    __tablename__ = "transmission_lines"

    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(150), nullable=False)
    from_substation_id = db.Column(db.Integer, db.ForeignKey("substations.id"), nullable=False, index=True)
    to_substation_id   = db.Column(db.Integer, db.ForeignKey("substations.id"), nullable=False, index=True)

    voltage_kv        = db.Column(db.Float, nullable=False)
    circuit_count     = db.Column(db.Integer, default=1)
    length_km         = db.Column(db.Float, nullable=False)
    conductor_type    = db.Column(db.String(60), nullable=True)

    thermal_rating_mva = db.Column(db.Float, nullable=True)
    current_flow_mva   = db.Column(db.Float, nullable=True)

    is_underground    = db.Column(db.Boolean, default=False)
    operator          = db.Column(db.String(120), nullable=True)
    in_service        = db.Column(db.Boolean, default=True)

    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    from_substation   = db.relationship("Substation", foreign_keys=[from_substation_id])
    to_substation     = db.relationship("Substation", foreign_keys=[to_substation_id])

    def to_dict(self) -> dict:
        return {
            "id":                 self.id,
            "name":               self.name,
            "from_substation_id": self.from_substation_id,
            "to_substation_id":   self.to_substation_id,
            "voltage_kv":         self.voltage_kv,
            "circuit_count":      self.circuit_count,
            "length_km":          self.length_km,
            "thermal_rating_mva": self.thermal_rating_mva,
            "current_flow_mva":   self.current_flow_mva,
            "is_underground":     self.is_underground,
            "in_service":         self.in_service,
        }
