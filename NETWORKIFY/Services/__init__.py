"""
Services package for PowerSys SaaS.

Each service is a pure-Python module (no Flask request handling) that
encapsulates one domain of business logic. Routes call services;
services call Models and pandapower; tasks call services.

Modules
-------
pandapower_service   : DB <-> pandapowerNet round-trip, IEEE templates
load_flow_service    : AC/DC power flow + violation extraction
short_circuit_service: IEC 60909 short-circuit analysis
contingency_service  : N-1 contingency scanning
opf_service          : Optimal power flow
timeseries_service   : Time-series simulation
feasibility_service  : Headline feature — facility-vs-grid feasibility
geo_service          : Haversine + bounding-box geo queries
osm_service          : OpenStreetMap Overpass import
report_service       : PDF (ReportLab) + Excel (openpyxl) generation
factory_presets      : Standard load profiles for small/medium/large
                        factories and data centres
"""

from .pandapower_service import PandapowerService
from .pandapower_service    import PandapowerService
from .load_flow_service     import LoadFlowService
from .short_circuit_service import ShortCircuitService
from .contingency_service   import ContingencyService
from .opf_service           import OPFService
from .timeseries_service    import TimeSeriesService
from .feasibility_service   import FeasibilityService
from .geo_service           import GeoService
from .osm_service           import OSMService
from .report_service        import ReportService
from .factory_presets       import FactoryPresets


__all__ = [
    "PandapowerService",
    "LoadFlowService",
    "ShortCircuitService",
    "ContingencyService",
    "OPFService",
    "TimeSeriesService",
    "FeasibilityService",
    "GeoService",
    "OSMService",
    "ReportService",
    "FactoryPresets",
]
