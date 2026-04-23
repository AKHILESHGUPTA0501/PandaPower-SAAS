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
    