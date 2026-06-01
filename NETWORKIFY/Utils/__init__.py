
"""
Utils package for PowerSys SaaS
Cross-cutting helpers used by Routes, Services, and Tasks:

  - constants       : magic numbers, defaults, voltage classes
  - logger          : structured logging configuration
  - error_handlers  : Flask error handler registration
  - decorators      : @role_required, @plan_required, @quota_check, etc.
  - validators      : pandapower-specific sanity checks
  - pandapower_helpers : conversions, naming, IEEE catalogue
  - audit           : audit-log recorder helper
  - responses       : ok() / fail() JSON response builders
"""
from .constants import *
from .logger import configure_logging, get_logger
from .responses import ok, fail, paginate_query
from .decorators import (
    admin_required,
    role_required,
    engineer_required,
    plan_required,
    quota_check,
    require_json,
    current_user,
)
from .validators import (
  validate_network_sanity,
  validate_load_flow_config,
  validate_short_circuit_config,
  validate_coordinates,
)
from .pandapower_helpers import (
  standard_voltage_levels,
  nearest_standard_voltage,
  line_std_types,
  transformer_std_types,
  estimate_power_factor,
  mva_to_amps,
)
from .audit import log_action, log_failed
from .error_handlers import register_error_handlers



__all__ = [
    "configure_logging", "get_logger",
    "ok", "fail", "paginate_query",
    "admin_required", "role_required", "engineer_required",
    "plan_required", "quota_check", "require_json", "current_user",
    "validate_network_sanity", "validate_load_flow_config",
    "validate_short_circuit_config", "validate_coordinates",
    "standard_voltage_levels", "nearest_standard_voltage",
    "line_std_types", "transformer_std_types",
    "estimate_power_factor", "mva_to_amps",
    "log_action", "log_failed",
    "register_error_handlers",
]


