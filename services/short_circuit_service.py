"""
ShortCircuitService — IEC 60909 short-circuit analysis via
pandapower.shortcircuit.calc_sc.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from extension import db
from Models import (
    AnalysisJob, AnalysisStatus,
    FaultResult, FaultType, Bus,
)
from .pandapower_service import PandapowerService


class ShortCircuitService:

    FAULT_TYPE_MAP = {
        "3ph":        FaultType.THREE_PHASE,
        "1ph":        FaultType.SINGLE_LINE_GROUND,
        "2ph":        FaultType.LINE_TO_LINE,
        "2ph_ground": FaultType.DOUBLE_LINE_GROUND,
    }

    PP_FAULT_NAME = {
        "3ph":        "3ph",
        "1ph":        "1ph",
        "2ph":        "2ph",
        "2ph_ground": "1ph",   # pandapower has no DLG; use SLG as fallback
    }

    @classmethod
    def run(cls, job_id: int) -> dict[str, Any]:
        import pandapower as pp
        import pandapower.shortcircuit as sc

        job = db.session.get(AnalysisJob, job_id)
        if job is None:
            raise ValueError(f"AnalysisJob {job_id} not found")

        cfg = job.config or {}
        fault_key = cfg.get("fault_type", "3ph")
        if fault_key not in cls.FAULT_TYPE_MAP:
            raise ValueError(f"Invalid fault_type: {fault_key}")
        case      = cfg.get("case", "max")
        buses_cfg = cfg.get("fault_buses") or []
        lv_tol    = cfg.get("lv_tol_percent", 10.0)

        job.status     = AnalysisStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()

        try:
            net = PandapowerService.build_net_from_db(job.network_id)

            sc.calc_sc(
                net,
                fault     = cls.PP_FAULT_NAME[fault_key],
                case      = case,
                lv_tol_percent = lv_tol,
                ip        = True,
                ith       = True,
            )

            results = cls._extract_results(net)
            job.results = results
            job.converged = True

            target_indices = (
                [int(b) for b in buses_cfg]
                if buses_cfg
                else list(net.res_bus_sc.index)
            )

            # Bus.id lookup for fault_bus_id FK
            bus_pp_to_id = {b.pp_index: b.id
                            for b in Bus.query
                                       .filter_by(network_id=job.network_id).all()}

            fault_type_enum = cls.FAULT_TYPE_MAP[fault_key]
            for ppi in target_indices:
                if ppi not in net.res_bus_sc.index:
                    continue
                row = net.res_bus_sc.loc[ppi]
                db.session.add(FaultResult(
                    job_id              = job.id,
                    fault_type          = fault_type_enum,
                    fault_bus_id        = bus_pp_to_id.get(int(ppi)),
                    fault_bus_pp_index  = int(ppi),
                    ikss_ka             = float(row.get("ikss_ka")) if "ikss_ka" in row else None,
                    skss_mw             = float(row.get("skss_mw")) if "skss_mw" in row else None,
                    ip_ka               = float(row.get("ip_ka"))   if "ip_ka"   in row else None,
                    ith_ka              = float(row.get("ith_ka"))  if "ith_ka"  in row else None,
                    ikss_min_ka         = float(row.get("ikss_min_ka")) if "ikss_min_ka" in row else None,
                    vm_pu               = None,
                    va_degree           = None,
                ))

            job.status       = AnalysisStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.duration_sec = (job.completed_at - job.started_at).total_seconds()
            job.progress_pct = 100.0
            db.session.commit()
            return {
                "job_id":       job.id,
                "fault_results":len(target_indices),
                "summary":      results.get("summary", {}),
            }
        except Exception as e:
            import traceback
            job.status         = AnalysisStatus.FAILED
            job.error_message  = str(e)
            job.error_traceback= traceback.format_exc()
            job.completed_at   = datetime.now(timezone.utc)
            db.session.commit()
            raise

    # -----------------------------------------------------------------
    @staticmethod
    def _extract_results(net) -> dict[str, Any]:
        def _df(tbl):
            return tbl.reset_index().to_dict("records") if tbl is not None and len(tbl) else []
        out = {
            "res_bus_sc":  _df(getattr(net, "res_bus_sc",  None)),
            "res_line_sc": _df(getattr(net, "res_line_sc", None)),
            "res_trafo_sc":_df(getattr(net, "res_trafo_sc",None)),
        }
        if hasattr(net, "res_bus_sc") and len(net.res_bus_sc):
            out["summary"] = {
                "max_ikss_ka":  float(net.res_bus_sc["ikss_ka"].max()),
                "min_ikss_ka":  float(net.res_bus_sc["ikss_ka"].min()),
                "max_ip_ka":    float(net.res_bus_sc["ip_ka"].max())   if "ip_ka" in net.res_bus_sc else None,
                "max_skss_mw":  float(net.res_bus_sc["skss_mw"].max()) if "skss_mw" in net.res_bus_sc else None,
                "bus_count":    int(len(net.res_bus_sc)),
            }
        return out
