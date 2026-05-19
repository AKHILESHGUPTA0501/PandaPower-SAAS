"""
ContingencyService — N-1 contingency analysis.

For each element in the scan list, outage it, run power flow, record
the post-contingency loading and voltages, and score the contingency
by violation count and severity.
"""
from __future__ import annotations
import copy
from datetime import datetime, timezone
from typing import Any

from extension import db
from Models import (
    AnalysisJob, AnalysisStatus,
    ContingencyResult, ElementType,
)
from .pandapower_service import PandapowerService

class ContingencyService:
    SUPPORTED_TYPES = {'line', 'trafo'}
    @classmethod
    def run(cls, job_id :int) -> dict[str, Any]:
        import pandapower as pp
        job = db.session.get(AnalysisJob,job_id)
        if job is None:
            raise ValueError(f"Analysisjob {job_id} not found")
        cfg =  job.config or {}
        loading_limit = float(cfg.get("check_loading_pct",100.0))
        v_min = float(cfg.get("check_v_min_pu", 0.95))
        v_max = float(cfg.get("check_v_max_pu",1.05))
        elements_cfg = cfg.get('elements') or []
        job.status = AnalysisStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()
        try:
            base_net = PandapowerService.build_net_from_db(job.network_id)
            if not elements_cfg:
                elements_cfg = []
                for ppi in base_net.line.index:
                    if base_net.line.loc[ppi].get("in_service", True):
                        elements_cfg.append({"type":"line", "pp_index": int(ppi)})
                for ppi in base_net.trafo.index:
                    if base_net.trafo.loc[ppi].get("in_service", True):
                        elements_cfg.append({"type": "trafo", "pp_index": int(ppi)})
            total = max(len(elements_cfg), 1)
            summary = {
                "total":             total,
                "scanned":           0,
                "with_violations":   0,
                "non_converging":    0,
                "worst_loading":     0.0,
                "worst_voltage_low": None,
                "worst_voltage_high":None,
            }
            for idx, elem in enumerate(elements_cfg, start = 1):
                etype = elem.get("type")
                pp_index = elem.get("pp_index")
                if etype not in cls.SUPPORTED_TYPES or pp_index is None:
                    continue
                net = copy.deepcopy(base_net)
                table = net.line if etype == 'line' else net.trafo
                name = str(table.loc[pp_index].get("name", f"{etype}_{pp_index}"))
                table.at[pp_index, 'in_service'] = False
                converged = True
                max_load = None
                min_v = None
                max_v = None
                violations = 0
                try:
                    pp.runpp(net)
                    converged = bool(getattr(net, 'converged', True))
                    if converged and len(net.res_bus):
                        min_v = float(net.res_bus['vm_pu'].min())
                        max_v = float(net.res_bus['vm_pu'].max())
                        loadings = []
                        if len(net.res_line): loading += list(net.res_line['loading_percent'])
                        if(net.res_trafo): loading += list(net.res_trafo['loading_percent'])
                        max_load = max(loadings) if loadings else 0.0
                        for v in net.res_bus['vm_pu']:
                            if v < v_min or v > v_max:
                                violations += 1
                        for ld in loadings:
                            if ld > loading_limit:
                                violations += 1
                except Exception:
                    converged = False
                    summary['non_converging'] +=1 
                
                risk_score = cls._risk_score(
                    converged, max_load, min_v, max_v,violations,
                    v_min, v_max, loading_limit,
                )
                db.session.add(ContingencyResult(
                    job_id               = job.id,
                    outaged_element_type = ElementType.LINE if etype == "line" else ElementType.TRANSFORMER,
                    outaged_pp_index     = int(pp_index),
                    outaged_name         = name,
                    converged            = converged,
                    max_loading_percent  = max_load,
                    min_vm_pu            = min_v,
                    max_vm_pu            = max_v,
                    violation_count      = violations,
                    risk_score           = risk_score,
                ))
                summary['scanned'] +=1
                if violations > 0:
                    summary['with_violations'] += 1
                if max_load is not None and max_load > summary['worst_loading']:
                    summary['worst_loading'] = max_load
                if min_v is not None and (summary['worst_voltage_low'] is None or min_v < summary['worst_voltage_low']):
                    summary['worst_voltage_low'] = min_v
                if max_v is not None and (summary['worst_voltage_high'] is None or max_v > summary['worst_voltage_high']):
                    summary['worst_voltage_high'] = max_v
                job.progress_pct = 100.0*idx/total
                if idx % 5 == 0:
                    db.session.commit()
            job.results = {'summary': summary}
            job.converged = True
            job.status = AnalysisStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.duration_sec = (job.completed_at - job.started_at).total_seconds()
            job.progress_pct = 100.0
            db.session.commit()
            return {'job_id': job.id, 'summary': summary}
        except Exception as e:
            import traceback
            job.status         = AnalysisStatus.FAILED
            job.error_message  = str(e)
            job.error_traceback= traceback.format_exc()
            job.completed_at   = datetime.now(timezone.utc)
            db.session.commit()
            raise
    
    @staticmethod
    def _risk_score(converged, max_load, min_v, max_v , violations
                    , v_min_lim, v_max_lim, load_lim) -> float:
        if not converged:
            return 1.0
        score = 0.0
        if max_load is not None and max_load > load_lim:
            score += min((max_load- load_lim)/50.0,0.4)
        if min_v is not None and min_v < v_min_lim:
            score == min((v_min_lim - min_v) / 0.1,0.3)
        if max_v is not None and max_v > v_max_lim:
            score += min((max_v - v_max_lim)/0.1,0.3)
        score += min(violations*0.01,0.2)
        return round(min(score,1.0),0.4)