"""
Facility + feasibility-study domain.

A consultant engineer creates a Facility (a proposed factory or
data centre at lat/lon with a target demand) and runs a
FeasibilityStudy against it. The study evaluates each nearby
Substation as a FeasibilityCheck row and assigns an overall verdict.

NOTE on naming:
  `FeasibilityCheck` is the per-substation row (one substation
  evaluated as a possible source). It is also exported as
  `FeasibilityCandidate` for callers that prefer that name.
"""
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum
from extension import db
from .models import (
    FacilityType,
    FacilitySize,
    FeasibilityVerdict,
)


# ---------------------------------------------------------------------
#  FACILITY
# ---------------------------------------------------------------------
class Facility(db.Model):
    """
    A proposed factory, data centre, or other large electrical load
    that the engineer wants to evaluate against the local grid.
    """
    __tablename__ = "facilities"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"),
                            nullable=False, index=True)
    project_id  = db.Column(db.Integer, db.ForeignKey("projects.id"),
                            nullable=True, index=True)

    # Basics
    name          = db.Column(db.String(160), nullable=False)
    description   = db.Column(db.Text, nullable=True)
    facility_type = db.Column(SAEnum(FacilityType),default=FacilityType.FACTORY, nullable=False)
    size_class    = db.Column(SAEnum(FacilitySize),default=FacilitySize.SMALL, nullable=False)

    # Geo
    latitude  = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address   = db.Column(db.String(300), nullable=True)
    city      = db.Column(db.String(80),  nullable=True)
    region    = db.Column(db.String(80),  nullable=True)
    country   = db.Column(db.String(60),  default="IN")

    # Electrical demand
    demand_mw               = db.Column(db.Float, nullable=False)
    demand_mvar             = db.Column(db.Float, nullable=True)
    power_factor            = db.Column(db.Float, default=0.9)
    required_voltage_kv     = db.Column(db.Float, nullable=True)
    redundancy_level        = db.Column(db.String(20), nullable=True)   # N / N+1 / 2N
    expected_load_factor    = db.Column(db.Float, nullable=True)
    operating_hours_per_day = db.Column(db.Float, default=24)

    # Data-centre specific (nullable so factories ignore them)
    dc_tier       = db.Column(db.String(10), nullable=True)  # Tier I-IV
    dc_pue        = db.Column(db.Float, nullable=True)
    dc_it_load_mw = db.Column(db.Float, nullable=True)

    # Factory specific
    factory_process_type  = db.Column(db.String(80), nullable=True)
    factory_shift_pattern = db.Column(db.String(40), nullable=True)

    # Planning
    target_commissioning_date = db.Column(db.Date,  nullable=True)
    estimated_capex_inr_lakh  = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime,default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc))

    owner   = db.relationship("Users",   back_populates="facilities")
    project = db.relationship("Project", back_populates="facilities")
    studies = db.relationship("FeasibilityStudy",back_populates="facility",cascade="all, delete-orphan")

    __table_args__ = (
        db.Index("ix_facility_lat_lon", "latitude", "longitude"),
    )

    @property
    def demand_mva(self) -> float:
        pf = self.power_factor or 0.9
        return self.demand_mw / pf if pf > 0 else self.demand_mw

    def to_dict(self):
        return {
            "id":            self.id,
            "name":          self.name,
            "description":   self.description,
            "facility_type": self.facility_type.value,
            "size_class":    self.size_class.value,
            "latitude":      self.latitude,
            "longitude":     self.longitude,
            "address":       self.address,
            "city":          self.city,
            "region":        self.region,
            "country":       self.country,
            "demand_mw":     self.demand_mw,
            "demand_mvar":   self.demand_mvar,
            "demand_mva":    self.demand_mva,
            "power_factor":  self.power_factor,
            "required_voltage_kv":     self.required_voltage_kv,
            "redundancy_level":        self.redundancy_level,
            "expected_load_factor":    self.expected_load_factor,
            "operating_hours_per_day": self.operating_hours_per_day,
            "dc_tier":       self.dc_tier,
            "dc_pue":        self.dc_pue,
            "dc_it_load_mw": self.dc_it_load_mw,
            "factory_process_type":  self.factory_process_type,
            "factory_shift_pattern": self.factory_shift_pattern,
            "target_commissioning_date":
                self.target_commissioning_date.isoformat()
                if self.target_commissioning_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Facility {self.name} {self.demand_mw}MW>"


# ---------------------------------------------------------------------
#  FEASIBILITY STUDY
# ---------------------------------------------------------------------
class FeasibilityStudy(db.Model):
    """
    A single 'can the grid power this site?' analysis run for a Facility.
    Backed by an AnalysisJob (analysis_type=FEASIBILITY) for Celery tracking.
    """
    __tablename__ = "feasibility_studies"

    id          = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"),
                            nullable=False, index=True)
    job_id      = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"),
                            nullable=True, index=True)

    # Search parameters
    search_radius_km     = db.Column(db.Float, default=15.0)
    max_voltage_drop_pct = db.Column(db.Float, default=5.0)
    min_headroom_factor  = db.Column(db.Float, default=1.2)   # require 20 % margin

    # Outcome
    verdict              = db.Column(SAEnum(FeasibilityVerdict),default=FeasibilityVerdict.INSUFFICIENT_DATA,nullable=False)
    chosen_substation_id = db.Column(db.Integer,db.ForeignKey("substations.id"),nullable=True)
    summary              = db.Column(db.Text,  nullable=True)
    recommendation       = db.Column(db.Text,  nullable=True)
    estimated_cost_inr_lakh  = db.Column(db.Float,   nullable=True)
    estimated_lead_time_days = db.Column(db.Integer, nullable=True)

    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)

    facility          = db.relationship("Facility",     back_populates="studies")
    job               = db.relationship("AnalysisJob")
    chosen_substation = db.relationship("Substation",
                                        foreign_keys=[chosen_substation_id])
    checks            = db.relationship("FeasibilityCheck",
                                        back_populates="study",
                                        cascade="all, delete-orphan",
                                        order_by="FeasibilityCheck.rank")

    def to_dict(self, include_checks: bool = True):
        data = {
            "id":          self.id,
            "facility_id": self.facility_id,
            "job_id":      self.job_id,
            "search_radius_km":     self.search_radius_km,
            "max_voltage_drop_pct": self.max_voltage_drop_pct,
            "min_headroom_factor":  self.min_headroom_factor,
            "verdict":              self.verdict.value,
            "chosen_substation_id": self.chosen_substation_id,
            "summary":              self.summary,
            "recommendation":       self.recommendation,
            "estimated_cost_inr_lakh":  self.estimated_cost_inr_lakh,
            "estimated_lead_time_days": self.estimated_lead_time_days,
            "check_count":  len(self.checks),
            "created_at":   self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        if include_checks:
            data["checks"] = [c.to_dict() for c in self.checks]
        return data


# ---------------------------------------------------------------------
#  FEASIBILITY CHECK  (one row per evaluated substation)
# ---------------------------------------------------------------------
class FeasibilityCheck(db.Model):
    """
    One Substation evaluated as a possible source for the Facility.
    Stored ordered by `rank` (1 = best fit).

    Also exported as `FeasibilityCandidate` for callers that prefer
    that name (see module-level alias at the bottom).
    """
    __tablename__ = "feasibility_checks"

    id            = db.Column(db.Integer, primary_key=True)
    study_id      = db.Column(db.Integer, db.ForeignKey("feasibility_studies.id"),nullable=False, index=True)
    substation_id = db.Column(db.Integer, db.ForeignKey("substations.id"),nullable=False, index=True)

    rank  = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float,   nullable=False)         # 0..1, higher = better

    # Distance + routing
    straight_distance_km = db.Column(db.Float, nullable=False)
    routed_distance_km   = db.Column(db.Float, nullable=True)

    # Electrical metrics
    headroom_mva        = db.Column(db.Float,   nullable=True)
    headroom_ratio      = db.Column(db.Float,   nullable=True)   # headroom / demand
    voltage_drop_pct    = db.Column(db.Float,   nullable=True)
    estimated_losses_kw = db.Column(db.Float,   nullable=True)
    short_circuit_ok    = db.Column(db.Boolean, nullable=True)

    verdict        = db.Column(SAEnum(FeasibilityVerdict),default=FeasibilityVerdict.INSUFFICIENT_DATA,nullable=False)
    reasons        = db.Column(db.Text, nullable=True)   # JSON list of strings
    upgrade_needed = db.Column(db.Text, nullable=True)   # JSON list of strings

    study      = db.relationship("FeasibilityStudy", back_populates="checks")
    substation = db.relationship("Substation",       back_populates="feasibility_checks")

    def to_dict(self):
        return {
            "id":            self.id,
            "study_id":      self.study_id,
            "substation_id": self.substation_id,
            "substation":    self.substation.to_dict() if self.substation else None,
            "rank":          self.rank,
            "score":         self.score,
            "straight_distance_km": self.straight_distance_km,
            "routed_distance_km":   self.routed_distance_km,
            "headroom_mva":         self.headroom_mva,
            "headroom_ratio":       self.headroom_ratio,
            "voltage_drop_pct":     self.voltage_drop_pct,
            "estimated_losses_kw":  self.estimated_losses_kw,
            "short_circuit_ok":     self.short_circuit_ok,
            "verdict":              self.verdict.value,
            "reasons":              self.reasons,
            "upgrade_needed":       self.upgrade_needed,
        }


# Backward-compatible alias — some code refers to this as `FeasibilityCandidate`.
FeasibilityCandidate = FeasibilityCheck
