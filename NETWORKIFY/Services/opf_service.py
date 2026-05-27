"""
OPFService — Optimal Power Flow (pandapower.runopp / rundcopp).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from extension import db
from Models import AnalysisJob, AnalysisStatus
from .pandapower_service import PandapowerService

class OPFService:
    SUPPORTED_OBJECTIVES = {'min_cost', 'min_lost'}
    @classmethod
    def run(cls, job_id :int) -> dict[str, Any]:
        import pandapower as pp
        job = db.session.get(AnalysisJob, job_id)
        if job is None:
            raise ValueError(f'AnalysisJob {job_id} not found')
        cfg = job.config or {}
        objective =  cfg.get('objective', 'min_cost')
        if objective not in cls.SUPPORTED_OBJECTIVES:
            raise ValueError(f'Unsupported Objective : {objective}')
        dc = bool(cfg.get('dc', False))
        job.status = AnalysisStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()
        try:
            net  = PandapowerService.build_net_from_db(job.network_id)
            if not hasattr(net, 'poly_cost') or len(net.poly_cost) == 0:
                for gi in net.gen.index:
                    pp.create_poly_cost(net, element= int(gi), et = 'gen',
                                        cp1_eur_per_mw= 10.0)
                for ei in net.ext_grid.index:
                    pp.create_poly_cost(net, element= int(ei), et = 'ext_grid', cp1_eur_per_mw= 10.0)
            if dc:
                pp.rundcopp(net)
            else:
                pp.runopp(net)
            converged = bool(getattr(net, 'OPF_CONVERGED', True))
            job.converged = converged
            results = cls._extract_results(net)
            job.results = results
            job.status = AnalysisStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.duration_sec = (job.completed_at - job.started_at).total_seconds()
            job.progress_pct = 100.0
            db.session.commit()
            return {'job_id' : job_id, 'converged': converged, 'results': results}
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
            "res_bus":     _df(getattr(net, "res_bus",      None)),
            "res_gen":     _df(getattr(net, "res_gen",      None)),
            "res_line":    _df(getattr(net, "res_line",     None)),
            "res_trafo":   _df(getattr(net, "res_trafo",    None)),
            "res_ext_grid":_df(getattr(net, "res_ext_grid", None)),
            "cost":        float(getattr(net, "res_cost", 0.0))
                            if hasattr(net, "res_cost") else None,
            "summary": {
                "total_cost":      float(getattr(net, "res_cost", 0.0)) if hasattr(net, "res_cost") else None,
                "total_p_gen_mw":  float(net.res_gen["p_mw"].sum()) if hasattr(net,"res_gen") and len(net.res_gen) else 0.0,
                "min_vm_pu":       float(net.res_bus["vm_pu"].min())if hasattr(net,"res_bus") and len(net.res_bus) else None,
                "max_vm_pu":       float(net.res_bus["vm_pu"].max())if hasattr(net,"res_bus") and len(net.res_bus) else None,
            },
        }