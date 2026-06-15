from datetime import datetime, timezone
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from extension import db
from Models import (
    PowerNetwork,
    AnalysisJob, AnalysisType, AnalysisStatus,
    Violation, FaultResult, ContingencyResult, TimeSeriesResult,
)
from ._helpers import (
    ok, fail,
    current_user,
    get_json_body,
    require_fields,
    paginate_query
)

analysis_bp = Blueprint("analysis", __name__, url_prefix = "/api/analyses")


#--------------------------------------------------------------
#--------------------HELPERS-----------------------------------
#-------------------------------------------------------------

def _accessible_network(network_id: int, user)-> PowerNetwork | None:
    net = db.session.get(PowerNetwork, network_id)
    if net is None:
        return None
    if net.user_id == user.id or user.is_admin:
        return net
    return None

def _owned_jobs(job_id : int, user)-> AnalysisJob | None:
    job = db.session.get(AnalysisJob, job_id)
    if job is None:
        return None
    if job.user_id == user.id or user.is_admin:
        return job
    return None

def _create_job(network_id : int, user_id : int, analysis_type : AnalysisType, config: dict)-> AnalysisJob:
    job = AnalysisJob(
        network_id = network_id,
        user_id = user_id,
        analysis_type = analysis_type,
        status = AnalysisStatus.PENDING,
    )
    job.config = config
    db.session.add(config)
    db.session.commit()
    return job 

#-----------------------------------------------------------------
#-------------------BASIC CRUD OPERATIONS FOR JOBS----------------
#-------------------------------------------------------------------

@analysis_bp.get('/')
@jwt_required()
def list_jobs():
    user = current_user()
    if user is None:
        return fail("Unauthorized",401)
    q= AnalysisJob.query
    if not user.is_admin:
        q = q.filter(AnalysisJob.user_id == user.id)
    if (atype := request.args.get('type')):
        try:
            q= q.filter(AnalysisJob.analysis_type == AnalysisType(atype))
        except ValueError:
            return fail(f'Invalid Analysis type {atype}', 400)
    if (status := request.args.get('status')):
        try:
            q= q.filter(AnalysisJob.status == AnalysisStatus(status))
        except ValueError:
            return fail(f"Invalid Status: {status}", 400)
    if (nid := request.args.get("network_id")):
        try:
            q= q.filter(AnalysisJob.network_id == int(nid))
        except ValueError:
            return fail("Network id must be int",400)
    q = q.order_by( AnalysisJob.created_at.desc())
    items , meta = paginate_query(q)
    return ok(
        data = {
            'jobs': [j.to_dict() for j in items]
        },
        pagination = meta
    )

@analysis_bp.get('/<int:job_id>')
@jwt_required()
def get_job(job_id : int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    job = _owned_jobs(job_id, user)
    if job is None:
        return fail("Job Not Found", 404)
    include_results = request.args.get("include_results", "true").lower()
    return ok(data= {
        "job": job.to_dict(include_results= include_results)})

@analysis_bp.delete('/<int:job_id>')
@jwt_required()
def delete_jobs(job_id : int):
    user = current_user()
    if user is None:
        return fail("UnAuthorized", 401)
    job = _owned_jobs(job_id, user)
    if job is None:
        return fail('No jobs Found', 404)
    if job.status == AnalysisStatus.RUNNING:
        return fail('Cannot delete a running job, cancel the job first', 409)
    db.session.delete(job)
    db.session.commit()
    return ok(message= "Job deleted")

@analysis_bp.post('/<int:job_id>/cancel')
@jwt_required()
def cancel_job(job_id:int):
    user = current_user()
    if user is None:
        return fail('UnAuthorized', 401)
    job = _owned_jobs(job_id, user)
    if job is None:
        return fail("Job Not found", 404)
    if job.status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, AnalysisStatus.CANCELLED):
        return fail(F"Job already {job.status.value}", 409)
    # TODO: revoking the celery after celery setup
    #celery.control.revoke(job.task_id, terminate = True)
    job.status = AnalysisStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(data = {"job": job.to_dict()}, message="Job cancelled")

#-------------------------------------------------------------------
#-------------------ANALYSIS TRIGGERS-----------------------------
#-------------------------------------------------------------------

@analysis_bp.post("/load-flow")
@jwt_required()
def run_load_flow():
    user = current_user()
    if user is None:
        return fail("Unauthorized",401)
    data = get_json_body()
    _, err = require_fields(data, ['network_id'])
    if err:
        return err
    net = _accessible_network(int(data['network_id'], user))
    if net is None:
        return fail('Network not Found', 404)
    algo = data.get("algorithm", "nr")
    if algo not in {"nr", "bfsw", "gs", "fdbx", "fdxb", "dc"}:
        return fail(f"Invalid Algorithm: {algo}", 400)
    config = {
        "algorithm": algo,
        "max_iteration": int(data.get("max_iteration", 50)),
        "tolerance_mva" : float(data.get("tolerance_mva", 1e-8)),
        "init": data.get('init', 'auto'),
        "check_violations": bool(data.get("check_violation", True)),
    }
    job = _create_job(net.id, user.id, AnalysisType.LOAD_FLOW, config)
    #TODO; task= run_load_flow_task.delay(job.id); job.task_id = task_id
    return ok(
        data={"job": job.to_dict()},
        message= "Load-Flow analysis queued",
        status=202
    )
@analysis_bp.post("/short-circuit")
@jwt_required()
def run_short_circuit():
    user = current_user()
    if user is None:
        return fail(
            "unauthorized", 401
        )
    data = get_json_body()
    _, err = require_fields(data, ['network_id'])
    if err:
        return err
    net = _accessible_network(int(data['network_id']), user)
    if net is None:
        return fail('Network not found', 404)
    fault_type = data.get("fault_type", "3ph")
    if fault_type not in {"3ph", "1ph", "2ph", "2ph_ground"}:
        return fail(f"Invalid Fault type :{fault_type}")
    case = data.get("case", "max")
    if case not in {"max","min"}:
        return fail(f"Invalid case : {case}", 400)
    config = {
        "fault_type": fault_type,
        "case": case,
        "fault_buses": data.get("fault_buses", []),
        "1v_tol_present": float(data.get("1v_tol_percent", 10.0)),
    }
    job = _create_job(net.id, user.id, AnalysisType.SHORT_CIRCUIT, config)
    return ok(
        data = {"job" : job.to_dict()},
        message = "Short-Circuit analysis queued",
        status= 202
    )

    
@analysis_bp.post('/contingency')
@jwt_required()
def run_contingency():
    user = current_user()
    if user is None:
        return fail('Unauthorized', 401)
    data = get_json_body()
    _, err = require_fields(data, ['network_id'])
    if err:
        return err
    net = _accessible_network(int(data['network_id']), user)
    if net is None:
        return fail('Network Not found', 404)
    config = {
        "elements": data.get("elements", []),
        "check_loading_pct": float(data.get("check_loading_pct", 100.0)),
        "check_vmin_pu": float(data.get("check_vmin_pu", 0.95)),
        "check_v_max_pu": float(data.get('Check_v_max_pu', 1.05)),
        }
    job = _create_job(net.id, user.id, AnalysisType.CONTINGENCY, config)
    return ok(
        data = {"job" : job.to_dict()},
        message= "Contingency Analysis queued",
        status = 202
    )

@analysis_bp.post('/opf')
@jwt_required()
def run_opf():
    user = current_user()
    if user is None:
        return fail('Unauthorized',401)
    data = get_json_body()
    _, err = require_fields(data, ["network_id"])
    if err:
        return err
    net = _accessible_network(int(data['network_id']), user)
    if net is None:
        return fail('No network Found',404)
    config = {
        "algorithm": data.get("algorithm","ipopt"),
        'objective': data.get("objective", "min_cost")
    }
    job = _create_job(net.id, user.id, AnalysisType.OPTIMAL_POWER_FLOW, config)
    return ok(
        data = {"job": job.to_dict()},
        message= "OPF Analysis Queued",
        status = 202
    )

@analysis_bp.post('/time_series')
@jwt_required()
def run_time_series():
    user = current_user()
    if user is None:
        return fail('Unauthorized',401)
    data = get_json_body()
    _, err = require_fields(data, ['network_id'])
    if err:
        return err
    net = _accessible_network(int(data['network_id']), user)
    if net is None:
        return fail('Network Not found', 404)
    steps = data.get("steps")
    if not steps:
        return fail("steps is required",400)
    try:
        steps = int(steps)
        if steps < 1 or steps > 8760:
            raise ValueError
    except (TypeError, ValueError):
        return fail("Steps must be an integer between 1 and 8760",400)
    config = {
        "steps": steps,
        "load_profiles": data.get("load_profiles",[]),
        "sgen_profiles": data.get("sgen_profiles",[]),
        'timestamps' : data.get('timestamps'),
        "variables": data.get(
            "variables",
            ["vm_pu", "loading_percent", "p_mw"],
        ),
    }
    job = _create_job(net.id, user.id, AnalysisType.TIME_SERIES, config)
    return ok(
        data = {"job": job.to_dict()},
        message= "Time series simulation queued",
        status = 202,
    )

#----------------------------------------------------------------
#------------------DETAIL RESULT ENDPOINT-----------------------
#-----------------------------------------------------------------

@analysis_bp.get('/<int:job_id>/violations')
@jwt_required()
def get_violations(job_id : int):
    user = current_user()
    if user is None:
        return fail('Unauthorized',401)
    job = _owned_jobs(job_id, user)
    if job is None:
        return fail('Job not Found',404)
    q = Violation.query.filter_by(job_id = job_id)
    if (sev:= request.args.get("severity")):
        q= q.filter(Violation.severity == sev)
    if (vtype:= request.args.get('type')):
        q=q.filter(Violation.violation_type == vtype)
    items = q.order_by(Violation.severity.desc()).all()
    return ok(data={'violations':[v.to_dict() for v in items]})

@analysis_bp.get('/<int:job_id>/fault-results')
@jwt_required()
def get_fault_result(job_id : int):
    user = current_user()
    if user is None:
        return fail('Unauthorized',401)
    job = _owned_jobs(job_id, user)
    if job is None:
        return fail('Job not found',404)
    items = FaultResult.query.filter_by(job_id= job_id).all()
    return ok(data = {'fault_results':[f.to_dict() for f in items]})

@analysis_bp.get('/<int:job_id>/contingency_results')
@jwt_required()
def get_contingency_results(job_id: int):
    user = current_user()
    if user is None:
        return fail('Unauthorized',401)
    job = _owned_jobs(job_id, user)
    if job is None:
        return fail('Job Not found',404)
    q= ContingencyResult.query.filter_by(job_id = job_id)
    if request.args.get("only_violations", "").lower() == 'true':
        q=q.filter(ContingencyResult.violation_count >0)
    items = q.order_by(ContingencyResult.risk_score.desc().nullslast()).all()
    return ok(data= {'contingency_result': [c.to_dict() for c in items]})
    
@analysis_bp.get('<int:job_id>/timeseries-result')
@jwt_required()
def get_timeseries_result(job_id : int):
    user = current_user()
    if user is None:
        return fail('Unauthorized',401)
    job = _owned_jobs(job_id, user)
    if job is None:
        return fail('No Jobs Found',404)
    include_series = request.args.get("include_series", "false").lower() == 'true'
    items = TimeSeriesResult.query.filter_by(job_id = job_id).all()
    return ok(data = {
        "results": [r.to_dict(include_series = include_series) for r in items],
    })