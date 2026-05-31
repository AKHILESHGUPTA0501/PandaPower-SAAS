'''
Analysis request and result schema
'''
from marshmallow import Schema, fields, validate

from Models import (
    AnalysisType, AnalysisStatus,
    ElementType, SeverityLevel, FaultType,
)

class AnalysisJobSchema(Schema):
    id = fields.Integer(dump_only= True)
    network_id = fields.Integer()
    user_id       = fields.Integer(dump_only=True)
    analysis_type = fields.String()
    status        = fields.String()
    task_id       = fields.String(allow_none=True)
    config        = fields.Dict(keys=fields.String(), values=fields.Raw())
    converged     = fields.Boolean(allow_none=True)
    error_message = fields.String(allow_none=True)
    progress_pct  = fields.Float()
    violation_count = fields.Integer(dump_only=True)
    duration_sec  = fields.Float(allow_none=True)
    created_at    = fields.String(allow_none=True)
    started_at    = fields.String(allow_none=True)
    completed_at  = fields.String(allow_none=True)
    results       = fields.Dict(required=False)

class LoadFlowRequestSchema(Schema):
    network_id = fields.Integer(required= True)
    algorithm = fields.String(
        load_default = 'nr',
        validate= validate.OneOf(['nr', 'bfsw', 'gs', 'fdbx', 'fdxb', 'dc'])
    )
    max_iteration = fields.Integer(load_default= 50, validate = validate.Range(min = 1, max = 500))
    tolerance_mva = fields.Float(load_default= 1e-8, validate = validate.Range(min = 1e-12, max = 1))
    init = fields.String(load_default='auto', validate = validate.OneOf(['auto', 'flat', 'dc', 'results']))
    check_violations = fields.Boolean(load_default= True)

class ShortCircuitRequestsSchema(Schema):
    network_id = fields.Integer(required= True)
    fault_type = fields.String(
        load_default= '3ph',
        validate = validate.OneOf(['3ph', '1ph', '2ph', '2ph_ground'])
    )
    case = fields.String(load_default= 'max', validate= validate.OneOf(['max', 'min']))
    fault_buses = fields.List(fields.Integer(), load_default= list)
    lv_tol_percent = fields.Float(load_default=10.0,
                                validate = validate.Range(min = 0.0, max = 50.0))
    
class ContingencyElementSchema(Schema):
    type = fields.String(required= True, validate= validate.OneOf(['line', 'trafo']))
    pp_index = fields.Integer(required= True, validate = validate.Range(min = 0))
    

class ContingencyRequestSchema(Schema):
    network_id        = fields.Integer(required=True)
    elements          = fields.List(fields.Nested(_ContingencyElementSchema),
                                    load_default=list)
    check_loading_pct = fields.Float(load_default=100.0,
                                     validate=validate.Range(min=10.0, max=300.0))
    check_v_min_pu    = fields.Float(load_default=0.95,
                                     validate=validate.Range(min=0.5, max=1.0))
    check_v_max_pu    = fields.Float(load_default=1.05,
                                     validate=validate.Range(min=1.0, max=1.5))


class OPFRequestSchema(Schema):
    network_id = fields.Integer(required=True)
    algorithm  = fields.String(load_default="ipopt",
                               validate=validate.OneOf(["ipopt", "interior"]))
    objective  = fields.String(load_default="min_cost",
                               validate=validate.OneOf(["min_cost", "min_loss"]))
    dc         = fields.Boolean(load_default=False)


class _ProfileSchema(Schema):
    pp_index = fields.Integer(required=True, validate=validate.Range(min=0))
    values   = fields.List(fields.Float(), required=True,
                           validate=validate.Length(min=1, max=8760))


class TimeSeriesRequestSchema(Schema):
    network_id    = fields.Integer(required=True)
    steps         = fields.Integer(required=True, validate=validate.Range(min=1, max=8760))
    load_profiles = fields.List(fields.Nested(_ProfileSchema), load_default=list)
    sgen_profiles = fields.List(fields.Nested(_ProfileSchema), load_default=list)
    timestamps    = fields.List(fields.String(), required=False, allow_none=True)
    variables     = fields.List(
        fields.String(validate=validate.OneOf(
            ["vm_pu", "va_degree", "loading_percent", "p_mw", "q_mvar", "pl_mw"]
        )),
        load_default=lambda: ["vm_pu", "loading_percent", "p_mw"],
    )


# =====================================================================
#  Result rows (output)
# =====================================================================
class ViolationSchema(Schema):
    id             = fields.Integer(dump_only=True)
    element_type   = fields.String()
    element_index  = fields.Integer()
    element_name   = fields.String(allow_none=True)
    violation_type = fields.String()
    severity       = fields.String()
    value          = fields.Float(allow_none=True)
    limit          = fields.Float(allow_none=True)
    unit           = fields.String(allow_none=True)
    message        = fields.String(allow_none=True)


class FaultResultSchema(Schema):
    id                 = fields.Integer(dump_only=True)
    fault_type         = fields.String()
    fault_bus_id       = fields.Integer(allow_none=True)
    fault_bus_pp_index = fields.Integer(allow_none=True)
    ikss_ka            = fields.Float(allow_none=True)
    skss_mw            = fields.Float(allow_none=True)
    ip_ka              = fields.Float(allow_none=True)
    ith_ka             = fields.Float(allow_none=True)
    ikss_min_ka        = fields.Float(allow_none=True)
    vm_pu              = fields.Float(allow_none=True)
    va_degree          = fields.Float(allow_none=True)


class ContingencyResultSchema(Schema):
    id                   = fields.Integer(dump_only=True)
    outaged_element_type = fields.String()
    outaged_pp_index     = fields.Integer()
    outaged_name         = fields.String(allow_none=True)
    converged            = fields.Boolean()
    max_loading_percent  = fields.Float(allow_none=True)
    min_vm_pu            = fields.Float(allow_none=True)
    max_vm_pu            = fields.Float(allow_none=True)
    violation_count      = fields.Integer()
    risk_score           = fields.Float(allow_none=True)


class TimeSeriesResultSchema(Schema):
    id               = fields.Integer(dump_only=True)
    element_type     = fields.String()
    element_pp_index = fields.Integer()
    element_name     = fields.String(allow_none=True)
    variable         = fields.String()
    min              = fields.Float(allow_none=True)
    max              = fields.Float(allow_none=True)
    mean             = fields.Float(allow_none=True)
    p95              = fields.Float(allow_none=True)
    series           = fields.List(fields.Float(allow_none=True), required=False)


# =====================================================================
#  Reports
# =====================================================================
class ReportSchema(Schema):
    id              = fields.Integer(dump_only=True)
    job_id          = fields.Integer()
    title           = fields.String()
    format          = fields.String()
    file_size_bytes = fields.Integer(allow_none=True)
    download_count  = fields.Integer()
    created_at      = fields.String(allow_none=True)


class ReportCreateSchema(Schema):
    job_id           = fields.Integer(required=True)
    format           = fields.String(load_default="pdf",
                                     validate=validate.OneOf(["pdf", "xlsx"]))
    title            = fields.String(required=False, allow_none=True,
                                     validate=validate.Length(max=200))
    include_diagrams = fields.Boolean(load_default=True)