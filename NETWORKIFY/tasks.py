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

def _complete_job(job : AnalysisJob):
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
@celery.task(bind = True, name = 'tasks.run_short-circuit')
def run_short_circuit(self, job_id : int):
    job = _start_job(job_id)
    _emit_progress(job_id, "Short Circuit Analysis....",5)
    try:
        config = job.config
        fault_type = config.get("fault_type", "3ph")
        bus_index = config.get("bus_index", None)
        _emit_progress(job_id, "Loading Network", 15)
        net = _load_net(job)

        _emit_progress(job_id, f"Computing {fault_type} Fault currents", 40)
        sc.calc_sc(
            net, 
            fault= fault_type,
            case= "max",
            ip= True,
            ith= True,
            bus = bus_index
        )
        _emit_progress(job_id, "Saving Fault results..", 70)
        fault_enum = FaultType(fault_type)
        for idx, row in net.res_bus_sc.iterrows():
            db.session.add(FaultResult(
                job_id = job.id,
                fault_type = fault_type,
                fault_bus_id = Bus.query.filter_by(network_id = job.network_id, pp_index = idx).first().id if Bus.query.filter_by(network_id = job.network_id, pp_index= idx).first() else None,
                ikss_ka = float(row.get("ikss_ka")),
                skss_mw = float(row.get("skss_mw")),
                ip_ka = float(row.get("ip_ka")),
                ith_ka = float(row.get("ith_ka")),
                raw_json = json.dumps(row.where(pd.notnull(row), None).to_dict())
            ))
        job.results_json = json.dumps({
                "fault_type":    fault_type,
                "bus_count":     len(net.res_bus_sc),
                "max_ikss_ka":   float(net.res_bus_sc["ikss_ka"].max()),
                "min_ikss_ka":   float(net.res_bus_sc["ikss_ka"].min()),
                "critical_bus":  int(net.res_bus_sc["ikss_ka"].idxmax()),
                "res_bus_sc":    json.loads(_df_to_json(net.res_bus_sc)),
            })
        db.session.commit()
        _complete_job(job)
        _emit_progress(job_id, "Short Circuit Analysis Complete", 100)
        _emit("analysis_complete", job_id, {
                "status" : 'complete',
                "fault_type" : fault_type,
                "critical_bus": int(net.res_bus_sc["ikss_ka"].idmax()),
                "max_ikss_ka": float(net.res_bus_sc["ikss_ka"].max())
            })
    except Exception as e:
        _fail_job(job, str(e))
        _emit("analysis_error", job_id, {'error':str(e)})
        raise

#-------------------------------------------------------
#--------------------N-1 CONTINGENCY --------------------
#-------------------------------------------------------
@celery.task(bind = True, name = "tasks.run_contingency")
def run_contingency(self, job_id:int):
    job = _start_job(job_id)
    _emit_progress(job_id, "Starting N-1 Contingency analysis...", 5)
    try:
        config = job.config
        v_min = float(config.get("v_min",0.95))
        v_max = float(config.get("v_max",1.05))
        net = _load_net(job)
        contingencies = []
        for idx, row in net.line.iterrows():
            contingencies.append((ElementType.LINE, idx, row.get("name", f"line_{idx}")))
        for idx, row in net.trafo.iterrows():
            contingencies.append((ElementType.TRANSFORMER, idx, row.get("name", f"trafo_{idx}")))
        total = len(contingencies)
        results = []
        all_results = []
        _emit_progress(job_id, f"Running {total} contingency cases...", 10)
        for i ,(elem_type, elem_idx, elem_name) in enumerate(contingencies):
            if elem_type == ElementType.LINE:
                net.line.at[elem_idx, "in_servicer"] = False
            else:
                net.trafo.at[elem_idx, "in_service"] = False
            converged = False
            max_loading = None
            min_vm = None
            max_vm = None
            violation_count = 0
            try:
                pp.runpp(net, algorithm="nr", numba = False)
                converged = net.converged
                if converged:
                    max_loading = float(net.res_line["loading_percent"].max()) if not net.res_line.empty else None
                    min_vm = float(net.res_bus["vm_pu"].min())
                    max_vm = float(net.res_bus["vm_pu"].max())
                    v_viols = ((net.res_bus["vm_pu"] < v_min) | (net.res_bus["vm_pu"] > v_max)).sum()
                    l_viols = (net.res_line["loading_percent"] > 100.0).sum() if not net.res_line.empty else 0
                    violation_count = int(v_viols + l_viols)
            except Exception:
                converged = False
            if elem_type == ElementType.LINE:
                net.line.at[elem_idx, "in_service"] = True
            else:
                net.trafo.at[elem_idx,"in_service"] = True
            risk_score = round((violation_count*10)+ (max_loading -100.0 if max_loading and max_loading > 100.0 else 0),2)
            cr = ContingencyResult(
                job_id               = job.id,
                outaged_element_type = elem_type,
                outaged_pp_index     = elem_idx,
                outaged_name         = elem_name,
                converged            = converged,
                max_loading_percent  = max_loading,
                min_vm_pu            = min_vm,
                max_vm_pu            = max_vm,
                violation_count      = violation_count,
                risk_score           = risk_score,
            )
            db.session.add(cr)
            all_results.append({
                "element":        elem_name,
                "type":           elem_type.value,
                "converged":      converged,
                "max_loading":    max_loading,
                "min_vm_pu":      min_vm,
                "violation_count":violation_count,
                "risk_score":     risk_score,
            })
            percent = 10 + int((i+ 1)/ total *85)
            _emit_progress(job_id, f"Contingency {i+1}/{total} : {elem_name}", percent)
        all_results.sort(key = lambda x : x["risk_score"], reverse = True)
        job.results_json = json.dumps({
            "total_contingencies": total,
            "failed_convergence":  sum(1 for r in all_results if not r["converged"]),
            "with_violations":     sum(1 for r in all_results if r["violation_count"] > 0),
            "top_risks":           all_results[:10],   # top 10 riskiest
        })
        db.session.commit()
        _complete_job(job)
        _emit_progress(job_id, "Contingency Analysis Completed", 100)
        _emit("analysis_complete", job_id , {
            "status" : "completed",
            "total_contingencies": total,
            "with_violations": sum(1 for r in all_results if r["violation_count"]> 0),
            "top_risk_element" : all_results[0]["element"] if all_results else None,
        })
    except Exception as e:
        _fail_job(job. str(e))
        _emit("analysis_error", job_id, {"error":str(e)})
        raise
#--------------------------------------------------------------
#--------------------OPTIMAL POWER FLOW------------------------
#--------------------------------------------------------------
@celery(bind= True, name = 'tasks.run_opf')
def run_opf(self, job_id :int):
    job = _start_job(job_id)
    _emit_progress(job_id, 'Starting Optimal Power Flow...', 5)
    try:
        _emit_progress(job_id, 'Loading Network', 15)
        net = _load_net(job)
        #---------Validate cost function exist----------
        if net.poly_cost.empty and net.pwl_cost.empty:
            raise ValueError(
                "No cost functions found."
                "Add Polynomial or Piecewise-linear costs to generators before running OPF"

            )
        #-------Base Case Load Flow First---------------
        _emit_progress(job_id, "Running Base case Load Flow", 30)
        pp.runpp(net, numba = False)
        base_gen_dispatch = net.res_gen["p_mw"].tolist() if not net.res_gen.empty else []
        base_loss = float(net.res_line["pl_mw"].sum()) if not net.res_line.empty else 0
        #----------Run OPF------------------------------------
        _emit_progress(job_id, "Running Optimal Power Flow.. (This May take a Moment)....", 55)
        pp.runopp(net, verbose= False, numba = False)
        if not net.OPF_converged:
            raise RuntimeError("OPF did not converge. Check generator limits and cost functions")
        #---------Extract results-------------------------
        _emit_progress(job_id, "Saving OPF results", 80)
        opf_gen_dispatch = net.res_gen['p_mw'].tolist() if not net.res_gen.empty else []
        opf_loss = float(net.res_line["pl_mw"].sum()) if not net.res_line.empty else 0
        total_cost = float(net.res_cost) if hasattr(net, "res_cost") else None

        
        job.results_json = json.dumps({
            "opf_converged":      True,
            "total_cost":         total_cost,
            "base_loss_mw":       base_loss,
            "opf_loss_mw":        opf_loss,
            "loss_reduction_mw":  round(base_loss - opf_loss, 4),
            "base_gen_dispatch":  base_gen_dispatch,
            "opf_gen_dispatch":   opf_gen_dispatch,
            "res_bus":  json.loads(_df_to_json(net.res_bus)),
            "res_gen":  json.loads(_df_to_json(net.res_gen)),
            "res_line": json.loads(_df_to_json(net.res_line)),
        })
        db.session.commit()
        _complete_job(job)
        _emit_progress(job_id, "OPF Completed", 100)
        _emit("Analysis Complete", job_id, {
            "status": "completed",
            "total_cost": total_cost,
            "loss_reduction_mw" : round(base_loss-opf_loss, 4),
        })
    except Exception as e:
        _fail_job(job, str(e))
        _emit("Analysis error", job_id, {"error": str(e)})
        raise

                    
