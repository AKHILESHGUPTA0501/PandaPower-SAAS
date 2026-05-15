"""
Analysis domain.

AnalysisJob is the root entity: every load-flow, short-circuit,
contingency, OPF, time-series, or feasibility run creates one.

Its detail rows (Violation, FaultResult, ContingencyResult,
TimeSeriesResult) hang off it; Report points back to it for
downloadable PDF / Excel artefacts.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum
from extension import db
from .models import (
    AnalysisType,
    AnalysisStatus,
    ElementType,
    FaultType,
    SeverityLevel,
)


# ---------------------------------------------------------------------
#  ANALYSIS JOB
# ---------------------------------------------------------------------
class AnalysisJob(db.Model):
    """
    Tracks one async analysis run. Celery task_id ties this row to a
    worker. results_json holds the full pandapower result tables as
    JSON for arbitrary later inspection; structured sub-tables
    (Violation, FaultResult, ContingencyResult, TimeSeriesResult)
    are populated for indexed querying.
    """
    __tablename__ = "analysis_jobs"

    id            = db.Column(db.Integer, primary_key=True)
    network_id    = db.Column(db.Integer, db.ForeignKey("power_networks.id"),nullable=False, index=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"),nullable=False, index=True)
    analysis_type = db.Column(SAEnum(AnalysisType), nullable=False, index=True)
    status        = db.Column(SAEnum(AnalysisStatus),default=AnalysisStatus.PENDING,nullable=False, index=True)
    task_id       = db.Column(db.String(64), nullable=True, index=True)  # Celery UUID

    # User-supplied parameters
    config_json   = db.Column(db.Text, nullable=True)
    # Full pandapower output (res_bus, res_line, res_trafo, ...)
    results_json  = db.Column(db.Text, nullable=True)

    # Convergence flag
    converged     = db.Column(db.Boolean, nullable=True)

    # Failure info
    error_message   = db.Column(db.Text, nullable=True)
    error_traceback = db.Column(db.Text, nullable=True)

    # Runtime
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at    = db.Column(db.DateTime, nullable=True)
    completed_at  = db.Column(db.DateTime, nullable=True)
    duration_sec  = db.Column(db.Float,   nullable=True)
    progress_pct  = db.Column(db.Float,   default=0.0)

    network       = db.relationship("PowerNetwork", back_populates="analyses")
    user          = db.relationship("Users",        back_populates="analyses")
    violations    = db.relationship("Violation",
                                    back_populates="job",
                                    cascade="all, delete-orphan")
    fault_results = db.relationship("FaultResult",
                                    back_populates="job",
                                    cascade="all, delete-orphan")
    contingency_results = db.relationship("ContingencyResult",back_populates="job",cascade="all, delete-orphan")
    timeseries_results  = db.relationship("TimeSeriesResult",back_populates="job",cascade="all, delete-orphan")
    reports             = db.relationship("Report",back_populates="job",cascade="all, delete-orphan")

    # ---- helpers ------------------------------------------------------
    @property
    def config(self) -> dict:
        return json.loads(self.config_json) if self.config_json else {}

    @config.setter
    def config(self, value: dict):
        self.config_json = json.dumps(value) if value is not None else None

    @property
    def results(self) -> dict:
        return json.loads(self.results_json) if self.results_json else {}

    @results.setter
    def results(self, value: dict):
        self.results_json = json.dumps(value, default=str) if value is not None else None

    def to_dict(self, include_results: bool = False) -> dict:
        data = {
            "id":            self.id,
            "network_id":    self.network_id,
            "user_id":       self.user_id,
            "analysis_type": self.analysis_type.value,
            "status":        self.status.value,
            "task_id":       self.task_id,
            "config":        self.config,
            "converged":     self.converged,
            "error_message": self.error_message,
            "progress_pct":  self.progress_pct,
            "violation_count": len(self.violations),
            "created_at":    self.created_at.isoformat()   if self.created_at   else None,
            "started_at":    self.started_at.isoformat()   if self.started_at   else None,
            "completed_at":  self.completed_at.isoformat() if self.completed_at else None,
            "duration_sec":  self.duration_sec,
        }
        if include_results:
            data["results"] = self.results
        return data

    def __repr__(self):
        return f"<AnalysisJob {self.analysis_type.value} status={self.status.value}>"


# ---------------------------------------------------------------------
#  VIOLATION
# ---------------------------------------------------------------------
class Violation(db.Model):
    """Single constraint violation flagged after an analysis run."""
    __tablename__ = "violations"

    id               = db.Column(db.Integer, primary_key=True)
    job_id           = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"),nullable=False, index=True)
    element_type     = db.Column(SAEnum(ElementType), nullable=False)
    element_pp_index = db.Column(db.Integer, nullable=False)
    element_name     = db.Column(db.String(120), nullable=True)
    violation_type   = db.Column(db.String(80), nullable=False, index=True)
    severity         = db.Column(SAEnum(SeverityLevel), nullable=False, index=True)
    value            = db.Column(db.Float, nullable=True)
    limit            = db.Column(db.Float, nullable=True)
    unit             = db.Column(db.String(20), nullable=True)
    message          = db.Column(db.Text, nullable=True)

    job              = db.relationship("AnalysisJob", back_populates="violations")

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


# ---------------------------------------------------------------------
#  FAULT RESULT (short-circuit analysis)
# ---------------------------------------------------------------------
class FaultResult(db.Model):
    """
    IEC 60909 short-circuit result per fault bus.
    Populated by pandapower.shortcircuit.calc_sc.
    """
    __tablename__ = "fault_results"

    id                 = db.Column(db.Integer, primary_key=True)
    job_id             = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"),nullable=False, index=True)
    fault_type         = db.Column(SAEnum(FaultType), nullable=False)
    fault_bus_id       = db.Column(db.Integer, db.ForeignKey("buses.id"), nullable=True)
    fault_bus_pp_index = db.Column(db.Integer, nullable=True)

    # IEC 60909 quantities
    ikss_ka     = db.Column(db.Float, nullable=True)   # initial SC current (kA)
    skss_mw     = db.Column(db.Float, nullable=True)   # initial SC power
    ip_ka       = db.Column(db.Float, nullable=True)   # peak SC current
    ith_ka      = db.Column(db.Float, nullable=True)   # thermal-equiv SC current
    ikss_min_ka = db.Column(db.Float, nullable=True)

    # Voltage during fault
    vm_pu     = db.Column(db.Float, nullable=True)
    va_degree = db.Column(db.Float, nullable=True)

    raw_json  = db.Column(db.Text, nullable=True)      # full row JSON

    job       = db.relationship("AnalysisJob", back_populates="fault_results")
    fault_bus = db.relationship("Bus", foreign_keys=[fault_bus_id])

    def to_dict(self):
        return {
            "id":           self.id,
            "fault_type":   self.fault_type.value,
            "fault_bus_id": self.fault_bus_id,
            "fault_bus_pp_index": self.fault_bus_pp_index,
            "ikss_ka": self.ikss_ka, "skss_mw": self.skss_mw,
            "ip_ka":   self.ip_ka,   "ith_ka":  self.ith_ka,
            "ikss_min_ka": self.ikss_min_ka,
            "vm_pu":   self.vm_pu,   "va_degree": self.va_degree,
        }


# ---------------------------------------------------------------------
#  CONTINGENCY RESULT (N-1)
# ---------------------------------------------------------------------
class ContingencyResult(db.Model):
    """One row per outaged element in an N-1 contingency scan."""
    __tablename__ = "contingency_results"

    id                   = db.Column(db.Integer, primary_key=True)
    job_id               = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"),nullable=False, index=True)
    outaged_element_type = db.Column(SAEnum(ElementType), nullable=False)
    outaged_pp_index     = db.Column(db.Integer, nullable=False)
    outaged_name         = db.Column(db.String(120), nullable=True)

    converged           = db.Column(db.Boolean, default=True, nullable=False)
    max_loading_percent = db.Column(db.Float, nullable=True)
    min_vm_pu           = db.Column(db.Float, nullable=True)
    max_vm_pu           = db.Column(db.Float, nullable=True)
    violation_count     = db.Column(db.Integer, default=0)
    risk_score          = db.Column(db.Float, nullable=True)
    results_json        = db.Column(db.Text, nullable=True)

    job = db.relationship("AnalysisJob", back_populates="contingency_results")

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


# ---------------------------------------------------------------------
#  TIME-SERIES RESULT
# ---------------------------------------------------------------------
class TimeSeriesResult(db.Model):
    """
    One aggregate row per element across a time-series simulation
    (pandapower.timeseries). The full per-step series is kept in
    series_json (a compact JSON list) to avoid a row explosion.
    """
    __tablename__ = "timeseries_results"

    id               = db.Column(db.Integer, primary_key=True)
    job_id           = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"),nullable=False, index=True)
    element_type     = db.Column(SAEnum(ElementType), nullable=False)
    element_pp_index = db.Column(db.Integer, nullable=False)
    element_name     = db.Column(db.String(120), nullable=True)
    variable         = db.Column(db.String(40), nullable=False)   # e.g. 'loading_percent'

    min_value  = db.Column(db.Float, nullable=True)
    max_value  = db.Column(db.Float, nullable=True)
    mean_value = db.Column(db.Float, nullable=True)
    p95_value  = db.Column(db.Float, nullable=True)

    # Compact time series aligned to job.config["timestamps"]
    series_json = db.Column(db.Text, nullable=True)

    job = db.relationship("AnalysisJob", back_populates="timeseries_results")

    def to_dict(self, include_series: bool = False):
        d = {
            "id":              self.id,
            "element_type":    self.element_type.value,
            "element_pp_index":self.element_pp_index,
            "element_name":    self.element_name,
            "variable":        self.variable,
            "min":  self.min_value,
            "max":  self.max_value,
            "mean": self.mean_value,
            "p95":  self.p95_value,
        }
        if include_series and self.series_json:
            d["series"] = json.loads(self.series_json)
        return d


# ---------------------------------------------------------------------
#  REPORT (PDF / Excel)
# ---------------------------------------------------------------------
class Report(db.Model):
    """Generated downloadable report tied to one AnalysisJob."""
    __tablename__ = "reports"

    id              = db.Column(db.Integer, primary_key=True)
    job_id          = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"),
                                nullable=False, index=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"),
                                nullable=False, index=True)
    title           = db.Column(db.String(200), nullable=False)
    format          = db.Column(db.String(10),  nullable=False)   # 'pdf' | 'xlsx'
    file_path       = db.Column(db.String(400), nullable=True)
    file_size_bytes = db.Column(db.Integer, nullable=True)
    download_count  = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    job  = db.relationship("AnalysisJob", back_populates="reports")
    user = db.relationship("Users",       back_populates="reports")

    def to_dict(self):
        return {
            "id":     self.id,
            "job_id": self.job_id,
            "title":  self.title,
            "format": self.format,
            "file_size_bytes": self.file_size_bytes,
            "download_count":  self.download_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
