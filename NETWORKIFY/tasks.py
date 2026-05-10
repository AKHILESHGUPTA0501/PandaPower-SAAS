import json
import time
from datetime import datetime, timezone
import pandapower as pp
import pandapower.shortcircuit as sc
import pandas as pd
from extension import celery, socketio, db
from Models.models import (
    AnalysisJob, AnalysisStatus, AnalysisType,
    Violation, FaultResult, ContingencyResult, Report,
    ElementType, SeverityLevel, FaultType, Bus, Line, Transformer
)
def _load_net(job : AnalysisJob) -> pp.pandapowerNet:
    return pp.from_json_string(job.network.net_json)

def _start_job(job_id : int) -> AnalysisJob:
    job = db.session.get(AnalysisJob, job_id)
    job.status = AnalysisStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    db.session.commit()
    return job

def complete_job(job : AnalysisJob):
    job.status = AnalysisStatus.COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    job.duration_sec = (job.completed_at - job.started_at).total_seconds()
    db.session.commit()

def _fail_job(job : AnalysisJob, error: str):
    job.status = AnalysisStatus.FAILED
    job.error_message = error
    job.completed_at = datetime.now(timezone.utc)
    db.session.commit()

def _emit(event: str, job_id : int, data : dict):
    socketio.emit(event, {"job_id": job_id, **data}, room = f"job_{job_id}")

def _emit_progress(job_id :int, message: str, percent : str):
    _emit("analysis Progress", job_id, {"message": message, "percent": percent})

def _df_to_json(df:pd.DataFrame):
    return df.where(pd.notnull(df), None).to_json(orient='records')

def _check_voltage_violations(
        job: AnalysisJob,
        net: pp.pandapowerNet,
        v_min : float= 0.95,
        v_max : float= 1.05,
):
    for idx, row in  net.res_bus.iterrows():
        vm = row["vm_pu"]
        if vm is None:
            continue
        if vm < v_min:
            db.session.add(Violation(
                job_id           = job.id,
                element_type     = ElementType.BUS,
                element_pp_index = idx,
                element_name     = net.bus.at[idx, "name"] if "name" in net.bus.columns else str(idx),
                violation_type   = "undervoltage",
                severity         = SeverityLevel.CRITICAL if vm < 0.90 else SeverityLevel.WARNING,
                value            = round(vm, 4),
                limit            = v_min,
                unit             = "pu",
                message          = f"Bus {idx} voltage {vm:.4f} pu is below minimum {v_min} pu.",
            ))
        elif vm > v_max:
            db.session.add(Violation(
                job_id           = job.id,
                element_type     = ElementType.BUS,
                element_pp_index = idx,
                element_name     = net.bus.at[idx, "name"] if "name" in net.bus.columns else str(idx),
                violation_type   = "overvoltage",
                severity         = SeverityLevel.CRITICAL if vm > 1.10 else SeverityLevel.WARNING,
                value            = round(vm, 4),
                limit            = v_max,
                unit             = "pu",
                message          = f"Bus {idx} voltage {vm:.4f} pu exceeds maximum {v_max} pu.",
            ))

def _check_line_violation(job: AnalysisJob, net : pp.pandapowerNet):
    for idx, row in net.res_line.iterrows():
        loading = row.get("loading_percent")
        if loading is None:
            continue
        if loading > 100.0:
            db.session.add(Violation(
                job_id = job.id,
                element_type = ElementType.LINE,
                element_pp_index = idx,
                element_name = net.line.at[idx, "name"] if "name" in net.line.columns else str(idx),
                violation_type = "thermal_overload",
                severity_level = SeverityLevel.CRITICAl if loading > 120.0 else SeverityLevel.WARNING,
                value = round(loading, 2),
                limit = 100.0,
                unit = '%',
                message = f"Line {idx} loading {loading:.1f}% exceeds thermal limit",
            ))

def _check_transformer_violations(job : AnalysisJob, net :pp.pandapowerNet):
    if net.res_trafo.empty:
        return
    for idx, row in net.res_trafo.iterrows():
        loading = row.get("loading_percent")
        if loading is None:
            continue
        if loading > 100.0:
            db.session.add(Violation(
                job_id = job.id,
                element_type     = ElementType.TRANSFORMER,
                element_pp_index = idx,
                element_name     = net.trafo.at[idx, "name"] if "name" in net.trafo.columns else str(idx),
                violation_type   = "transformer_overload",
                severity         = SeverityLevel.CRITICAL if loading > 120.0 else SeverityLevel.WARNING,
                value            = round(loading, 2),
                limit            = 100.0,
                unit             = "%",
                message          = f"Transformer {idx} loading {loading:.1f}% exceeds limit.",
            ))


#-------------------------------------------------------------
#       LOAD FLOW ANALYSIS
#-------------------------------------------------------------

@celery.task(bind = True, name = "tasks.run_load_flow")
def run_load_flow(self, job_id : int):
    job = _start_job(job_id)
    _emit_progress(job_id, "Starting Load Flow Analysis ....", 5)
    try:
        config = job.config
        algorithm = config.get("algorithm", "nr")
        v_min = float(config.get("v_min", 0.95))
        v_max = float(config.get("v_max", 1.05))
        _emit_progress(job_id, "Loading Network Topology....", 15)
        net = _load_net(job)
# Running Power Flow Analysis
        _emit_progress(job_id, f"Running {algorithm.upper()} power flow...", 35)
        pp.runpp(net, algorithm= algorithm, numba= False)

        if not net.converged:
            raise RuntimeError("Load Flow Did not converge, Check Network Configuration")
        # -------------STORE RESULTS----------------
        _emit_progress(job_id, "Saving results...", 60)
        results = {
            "res_bus " : json.loads(_df_to_json(net.res_bus)),
            "res_line" : json.loads(_df_to_json(net.res_line)),
            "res_trafo": json.loads(_df_to_json(net.res_trafo)),
            "res_ext_grid": json.loads(_df_to_json(net.res_ext_grid)),
            "converged" : net.converged,
            "total_load_flow": float(net.res_load["p_mw"].sum()) if not net.res_load.empty else 0,
            "total_gen_mw": float(net.res_gen["p_mw"].sum()) if not net.res_gen.empty else 0
        }
        job.results_json = json.dumps(results)
        #------------------Check Violations------------------
        _emit_progress(job_id, "Checking Constraints Violations...", 80)
        _check_voltage_violations(job, net, v_min, v_max)
        _check_line_violation(job, net)
        _check_transformer_violations(job, net)
        db.session.commit()
        #-----------Done-------------------
        -complete_job(job)
        _emit_progress(job_id, "Load Flow Completed",100)
        violation_count = Violation.query.filter_by(job_id=job_id).count()
        _emit('Analysis Completed', job_id, {
            'status': "completed",
            "converged": True,
            "violation_count": violation_count,
            "total_loss_mw" : results["total_loss_mw"]
        })
    except Exception as e:
        _fail_job(job, str(e))
        _emit("analysis error", job_id, {"error":str(e)})
        raise

#-----------------------------------------------------------
#----------------------SHORT CIRCUIT-----------------------
#-----------------------------------------------------------