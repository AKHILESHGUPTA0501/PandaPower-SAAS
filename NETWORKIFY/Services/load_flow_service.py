"""
LoadFlowService — runs pandapower power-flow and converts results
into AnalysisJob.results + Violation rows.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from extension import db
from Models import (
    AnalysisJob, AnalysisStatus,
    Violation, ElementType, SeverityLevel,
)
from .pandapower_service import PandapowerService

class LoadFlowService:

    SUPPORTED_ALGORITHMS = {"nr", "bfsw", "gs", "fdbx", "fdxb", "dc"}
    @classmethod 
    def run(cls, job_id:int)-> dict[str, Any]:
        import pandapower as pp
        job = db.session.get(AnalysisJob, job_id)
        if job is None:
            raise ValueError(f'AnalysisJob {job_id} not found')
        cfg = job.config or {}
        algo = cfg.get('algorithm', 'nr')
        if algo not in cls.SUPPORTED_ALGORITHMS:
            raise ValueError(f'Unsupported Algorithms : {algo}')
        job.status = AnalysisStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()
        try:
            net = PandapowerService.build_net_from_db(job.network_id)
            kwargs = dict(
                algorithm    = algo,
                max_iteration= cfg.get("max_iteration", 50),
                tolerance_mva= cfg.get("tolerance_mva", 1e-8),
                init         = cfg.get("init", "auto"),
            )
            if algo == 'dc':
                pp.rundcpp(net)
            else:
                pp.runpp(net, **kwargs)
            converged = bool(getattr(net, 'converged', True))
            job.converged = converged
            results = cls._extract_results(net)
            job.results = results
            if cfg.get('check_violations', True):
                cls._record_violations(job, net)
            

            job.status = AnalysisStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.duration_check = (job.completed_at -job.started_at).total_seconds()
            job.progress_pct = 100.0
            db.session.commit()
            return {
                "job_id":         job.id,
                "converged":      converged,
                "violation_count":len(job.violations),
                "results":        results,
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
    def _extract_results(net) -> dict[str, Any]:
        def _df(tbl):
            return tbl.reset_index().to_dict("records") if tbl is not None and len(tbl) else []
        return {
            "res_bus":      _df(getattr(net, "res_bus", None)),
            "res_line":     _df(getattr(net, "res_line", None)),
            "res_trafo":    _df(getattr(net, "res_trafo", None)),
            "res_load":     _df(getattr(net, "res_load", None)),
            "res_gen":      _df(getattr(net, "res_gen", None)),
            "res_ext_grid": _df(getattr(net, "res_ext_grid", None)),
            "summary": {
                "total_p_load_mw":   float(net.res_load["p_mw"].sum())  if len(net.res_load) else 0.0,
                "total_q_load_mvar": float(net.res_load["q_mvar"].sum())if len(net.res_load) else 0.0,
                "total_p_gen_mw":    float(net.res_gen["p_mw"].sum())   if len(net.res_gen)  else 0.0,
                "total_p_loss_mw":   float(net.res_line["pl_mw"].sum() +
                                            net.res_trafo["pl_mw"].sum())
                                    if len(net.res_line) and len(net.res_trafo) else 0.0,
                "min_vm_pu":         float(net.res_bus["vm_pu"].min())  if len(net.res_bus) else None,
                "max_vm_pu":         float(net.res_bus["vm_pu"].max())  if len(net.res_bus) else None,
                "max_line_loading":  float(net.res_line["loading_percent"].max()) if len(net.res_line) else None,
                "max_trafo_loading": float(net.res_trafo["loading_percent"].max())if len(net.res_trafo) else None,
            },
        }

    @staticmethod
    def _record_violations(job: AnalysisJob, net) -> None:
        # Bus voltage limits
        for ppi, row in net.res_bus.iterrows():
            vm = row["vm_pu"]
            bus_meta = net.bus.loc[ppi]
            v_min = bus_meta.get("min_vm_pu", 0.95)
            v_max = bus_meta.get("max_vm_pu", 1.05)
            name  = bus_meta.get("name", f"bus_{ppi}")
            if vm < v_min:
                db.session.add(Violation(
                    job_id=job.id, element_type=ElementType.BUS,
                    element_pp_index=int(ppi), element_name=str(name),
                    violation_type="undervoltage",
                    severity=SeverityLevel.CRITICAL if vm < 0.9 else SeverityLevel.WARNING,
                    value=float(vm), limit=float(v_min), unit="pu",
                    message=f"Bus voltage {vm:.3f} pu below limit {v_min}",
                ))
            elif vm > v_max:
                db.session.add(Violation(
                    job_id=job.id, element_type=ElementType.BUS,
                    element_pp_index=int(ppi), element_name=str(name),
                    violation_type="overvoltage",
                    severity=SeverityLevel.CRITICAL if vm > 1.1 else SeverityLevel.WARNING,
                    value=float(vm), limit=float(v_max), unit="pu",
                    message=f"Bus voltage {vm:.3f} pu above limit {v_max}",
                ))

        # Line loading
        for ppi, row in net.res_line.iterrows():
            loading = row["loading_percent"]
            if loading > 100:
                name = net.line.loc[ppi].get("name", f"line_{ppi}")
                db.session.add(Violation(
                    job_id=job.id, element_type=ElementType.LINE,
                    element_pp_index=int(ppi), element_name=str(name),
                    violation_type="overload",
                    severity=SeverityLevel.CRITICAL if loading > 120 else SeverityLevel.WARNING,
                    value=float(loading), limit=100.0, unit="%",
                    message=f"Line loading {loading:.1f}% exceeds 100%",
                ))

        # Transformer loading
        for ppi, row in net.res_trafo.iterrows():
            loading = row["loading_percent"]
            if loading > 100:
                name = net.trafo.loc[ppi].get("name", f"trafo_{ppi}")
                db.session.add(Violation(
                    job_id=job.id, element_type=ElementType.TRANSFORMER,
                    element_pp_index=int(ppi), element_name=str(name),
                    violation_type="overload",
                    severity=SeverityLevel.CRITICAL if loading > 120 else SeverityLevel.WARNING,
                    value=float(loading), limit=100.0, unit="%",
                    message=f"Transformer loading {loading:.1f}% exceeds 100%",
                ))