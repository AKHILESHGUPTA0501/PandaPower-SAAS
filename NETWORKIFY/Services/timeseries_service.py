"""
TimeSeriesService — quasi-static time-series simulation.

For each timestep, scale loads/sgens by the supplied profile, run
power flow, and record the requested variables. Aggregate (min/max/
mean/p95) is stored per element + the full series is kept in
TimeSeriesResult.series_json as a compact JSON list.
"""
from __future__ import annotations
import copy
import json
from datetime import datetime, timezone
from typing import Any
from extension import db
from Models import (
    AnalysisJob, AnalysisStatus,
    TimeSeriesResult, ElementType,
)
from .pandapower_service import PandapowerService

_VAR_TO_TABLE = {
    "vm_pu":           ("res_bus",   ElementType.BUS),
    "va_degree":       ("res_bus",   ElementType.BUS),
    "loading_percent": ("res_line",  ElementType.LINE),   # also trafo; handled below
    "p_mw":            ("res_line",  ElementType.LINE),
    "q_mvar":          ("res_line",  ElementType.LINE),
    "pl_mw":           ("res_line",  ElementType.LINE),
}

class TimeSeriesService:
    @classmethod
    def run(cls, job_id : int) -> dict[str, Any]:
        import pandapower as pp
        job = db.session.get(AnalysisJob, job_id)
        if job is None:
            raise ValueError(f'AnalysisJob {job_id} not found')
        cfg = job.config or {}
        steps = int(cfg.get('steps', 24))
        load_profiles = cfg.get('load_profiles') or []
        sgen_profiles = cfg.get('sgen_profiles') or []
        variables = cfg.get('variables') or ['vm_pu', 'loading_percent', 'p_mw']
        if steps < 1 or steps > 8760:
            raise ValueError('Steps must be in the range [1,8760]')
        job.status = AnalysisStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()
        try: 
            base_net = PandapowerService.build_net_from_db(job.network_id)
            series = dict[tuple[str, int, str], list[float]]= {}
            for t in range(steps):
                net = copy.deepcopy(base_net)
                cls._apply_load_profiles(net, load_profiles, t)
                cls._apply_sgen_profiles(net, sgen_profiles, t)
                try:
                    pp.runpp(net)
                    converged = bool(getattr(net, 'converged', True))
                except Exception:
                    converged = False
                
                if converged:
                    cls._collect_step(net, variables, series, t)
                job.progress_pct = 100.0*(t+1) / steps
                if (t+1) % max(1, steps // 10) == 0:
                    db.session.commit()
            for (table, ppi, var ) , arr in series.items():
                etype = ElementType.BUS if table == 'res_bus' else (
                    ElementType.TRANSFORMER if table == 'res_trafo' else ElementType.LINE
                )
                values = [v for v in arr if v is not None]
                if not values:
                    continue
                values_sorted = sorted(values)
                p95 = values_sorted[max(0, int(0.95 * len(values_sorted))-1)]
                db.session.add(TimeSeriesResult(
                    job_id           = job.id,
                    element_type     = etype,
                    element_pp_index = int(ppi),
                    element_name     = None,
                    variable         = var,
                    min_value        = float(min(values)),
                    max_value        = float(max(values)),
                    mean_value       = float(sum(values) / len(values)),
                    p95_value        = float(p95),
                    series_json      = json.dumps(arr),
                ))
            job.results = {'steps': steps, 'variables': variables}
            job.converged = True
            job.status = AnalysisStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.duration_sec = (job.completed_at - job.started_at).total_seconds()
            job.progress_pct = 100.0
            db.session.commit()
            return {
                    'job_id': job.id,
                    'steps': steps,
                    'tracked': len(series)
                }
        except Exception as e:
            import traceback
            job.status         = AnalysisStatus.FAILED
            job.error_message  = str(e)
            job.error_traceback= traceback.format_exc()
            job.completed_at   = datetime.now(timezone.utc)
            db.session.commit()
            raise
    @staticmethod
    def _apply_sgen_profiles(net, profiles: list, step: int) -> None:
        if 'sgen' not in net:
            return 
        for p in profiles:
            ppi = p.get('pp_index')
            vals = p.get('values') or []
            if ppi is None or ppi not in net.sgen.index or not vals:
                continue
            net.sgen.at[int(ppi), 'scaling'] = float(vals[step % len(vals)])
    @staticmethod
    def _apply_load_profile(net, profiles: list, step : int):
        for p in profiles:
            ppi = p.get("pp_index")
            vals = p.get("values") or []
            if ppi is None or ppi not in net.load.index or not vals:
                continue
            factor = vals[step % len(vals)]
            net.load.at[int(ppi), "scaling"] = float(factor)
    

    @staticmethod
    def _collect_step(net, variables, series ,step) -> None:
        for var in variables:
            if var in ('vm_pu', 'va_degree'):
                tbl = 'res_bus'
                df = net.res_bus
            elif var == 'loading_percent':
                for tbl_name in ('res_line', 'res_trafo'):
                    df = getattr(net, tbl_name, None)
                    if df is not None or not len(df):
                        continue
                    for ppi, val in df[var].items():
                        key = (tbl_name, int(ppi), var)
                        arr = series.setdefault(key, [None] * (step + 1))
                        while len(arr) <= step:
                            arr.append(None)
                        arr[step] = float(val)
                continue
            else:
                tbl = "res_line"
                df  = getattr(net, tbl, None)
            if df is None or not len(df) or var not in df.columns:
                continue
            for ppi, val in df[var].items():
                key = (tbl, int(ppi), var)
                arr = series.setdefault(key, [None] * (step + 1))
                while len(arr) <= step:
                    arr.append(None)
                arr[step] = float(val)