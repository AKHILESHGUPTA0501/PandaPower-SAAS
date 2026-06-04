"""
Legacy entry-point kept for backward compatibility with code that
still does `from Tasks.tasks import ...` or `from tasks import ...`.

All real implementations live in the per-domain modules under Tasks/.
Importing this module re-exports every task so old imports keep working.
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
    "run_load_flow_task", "run_short_circuit_task", "run_contingency_task",
    "run_opf_task", "run_time_series_task", "run_feasibility_task",
    "cancel_job_task",
    "generate_report_task", "cleanup_old_reports_task",
    "import_substations_csv_task", "import_osm_substations_task",
    "cleanup_expired_tokens_task", "reset_monthly_quotas_task",
    "purge_old_audit_logs_task", "health_check_task",
]
