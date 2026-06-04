"""
Tasks package for PowerSys SaaS.

Celery tasks split by domain:

  - tasks.py         : legacy module kept for backward compat (your
                       existing imports). Re-exports everything below.
  - analysis_tasks   : load-flow, short-circuit, contingency, OPF,
                       time-series, feasibility (the headline)
  - report_tasks     : PDF / Excel report generation
  - import_tasks     : CSV upload + OSM Overpass import
  - maintenance_tasks: periodic cleanup, quota resets, health checks

Every task is wired with Flask app context via the ContextTask base
class defined in extension.py.
"""
from .analysis_tasks import (
    run_load_flow_task,
    run_short_circuit_task,
    run_contingency_task,
    run_opf_task,
    run_time_series_task,
    run_feasibility_task,
    cancel_job_task,
)
from .report_tasks import (
    generate_report_task,
    cleanup_old_reports_task,
)
from .import_tasks import (
    import_substations_csv_task,
    import_osm_substations_task,
)
from .maintenance_tasks import (
    cleanup_expired_tokens_task,
    reset_monthly_quotas_task,
    purge_old_audit_logs_task,
    health_check_task,
)

__all__ = [
    # analysis
    "run_load_flow_task", "run_short_circuit_task", "run_contingency_task",
    "run_opf_task", "run_time_series_task", "run_feasibility_task",
    "cancel_job_task",
    # report
    "generate_report_task", "cleanup_old_reports_task",
    # import
    "import_substations_csv_task", "import_osm_substations_task",
    # maintenance
    "cleanup_expired_tokens_task", "reset_monthly_quotas_task",
    "purge_old_audit_logs_task", "health_check_task",
]

