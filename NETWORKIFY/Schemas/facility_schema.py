"""
Facility and feasibility-study schemas.
"""
from marshmallow import Schema, fields, validate, validates_schema, ValidationError

from Models import (
    FacilityType, FacilitySize, FeasibilityVerdict,
)


# =====================================================================
#  FACILITY
# =====================================================================
class FacilitySchema(Schema):
    id                       = fields.Integer(dump_only=True)
    user_id                  = fields.Integer(dump_only=True)
    project_id               = fields.Integer(allow_none=True)
    name                     = fields.String()
    description              = fields.String(allow_none=True)
    facility_type            = fields.String()
    size_class               = fields.String()
    latitude                 = fields.Float()
    longitude                = fields.Float()
    address                  = fields.String(allow_none=True)
    city                     = fields.String(allow_none=True)
    region                   = fields.String(allow_none=True)
    country                  = fields.String()
    demand_mw                = fields.Float()
    demand_mvar              = fields.Float(allow_none=True)
    demand_mva               = fields.Float(dump_only=True)
    power_factor             = fields.Float()
    required_voltage_kv      = fields.Float(allow_none=True)
    redundancy_level         = fields.String(allow_none=True)
    expected_load_factor     = fields.Float(allow_none=True)
    operating_hours_per_day  = fields.Float()
    dc_tier                  = fields.String(allow_none=True)
    dc_pue                   = fields.Float(allow_none=True)
    dc_it_load_mw            = fields.Float(allow_none=True)
    factory_process_type     = fields.String(allow_none=True)
    factory_shift_pattern    = fields.String(allow_none=True)
    target_commissioning_date= fields.String(allow_none=True)
    created_at               = fields.String(dump_only=True)


class FacilityCreateSchema(Schema):
    name        = fields.String(required=True, validate=validate.Length(min=1, max=160))
    description = fields.String(required=False, allow_none=True)
    facility_type = fields.String(
        load_default="factory",
        validate=validate.OneOf([t.value for t in FacilityType]),
    )
    size_class    = fields.String(
        required=False,
        validate=validate.OneOf([s.value for s in FacilitySize]),
    )
    latitude  = fields.Float(required=True, validate=validate.Range(min=-90.0,  max=90.0))
    longitude = fields.Float(required=True, validate=validate.Range(min=-180.0, max=180.0))
    address   = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
    city      = fields.String(required=False, allow_none=True, validate=validate.Length(max=80))
    region    = fields.String(required=False, allow_none=True, validate=validate.Length(max=80))
    country   = fields.String(load_default="IN", validate=validate.Length(max=60))

    demand_mw     = fields.Float(required=True, validate=validate.Range(min=0.001, max=10000.0))
    demand_mvar   = fields.Float(required=False, allow_none=True)
    power_factor  = fields.Float(load_default=0.9, validate=validate.Range(min=0.1, max=1.0))
    required_voltage_kv  = fields.Float(required=False, allow_none=True,
                                        validate=validate.Range(min=0.1, max=1500.0))
    redundancy_level     = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(["N", "N+1", "2N", "2N+1", None]),
    )
    expected_load_factor = fields.Float(required=False, allow_none=True,
                                        validate=validate.Range(min=0.0, max=1.0))
    operating_hours_per_day = fields.Float(load_default=24,
                                           validate=validate.Range(min=0.0, max=24.0))

    # Data-centre fields
    dc_tier       = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(["I", "II", "III", "IV", None]),
    )
    dc_pue        = fields.Float(required=False, allow_none=True,
                                 validate=validate.Range(min=1.0, max=5.0))
    dc_it_load_mw = fields.Float(required=False, allow_none=True,
                                 validate=validate.Range(min=0.0))

    # Factory fields
    factory_process_type  = fields.String(required=False, allow_none=True,
                                          validate=validate.Length(max=80))
    factory_shift_pattern = fields.String(required=False, allow_none=True,
                                          validate=validate.Length(max=40))

    target_commissioning_date = fields.Date(required=False, allow_none=True)
    estimated_capex_inr_lakh  = fields.Float(required=False, allow_none=True,
                                             validate=validate.Range(min=0.0))
    project_id = fields.Integer(required=False, allow_none=True)


class FacilityUpdateSchema(Schema):
    name        = fields.String(required=False, validate=validate.Length(min=1, max=160))
    description = fields.String(required=False, allow_none=True)
    facility_type = fields.String(
        required=False,
        validate=validate.OneOf([t.value for t in FacilityType]),
    )
    size_class  = fields.String(
        required=False,
        validate=validate.OneOf([s.value for s in FacilitySize]),
    )
    latitude    = fields.Float(required=False, validate=validate.Range(min=-90.0,  max=90.0))
    longitude   = fields.Float(required=False, validate=validate.Range(min=-180.0, max=180.0))
    address     = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
    city        = fields.String(required=False, allow_none=True, validate=validate.Length(max=80))
    region      = fields.String(required=False, allow_none=True, validate=validate.Length(max=80))
    country     = fields.String(required=False, validate=validate.Length(max=60))

    demand_mw   = fields.Float(required=False, validate=validate.Range(min=0.001, max=10000.0))
    demand_mvar = fields.Float(required=False, allow_none=True)
    power_factor= fields.Float(required=False, validate=validate.Range(min=0.1, max=1.0))
    required_voltage_kv  = fields.Float(required=False, allow_none=True,
                                        validate=validate.Range(min=0.1, max=1500.0))
    redundancy_level     = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(["N", "N+1", "2N", "2N+1", None]),
    )
    expected_load_factor = fields.Float(required=False, allow_none=True,
                                        validate=validate.Range(min=0.0, max=1.0))
    operating_hours_per_day = fields.Float(required=False,
                                           validate=validate.Range(min=0.0, max=24.0))

    dc_tier       = fields.String(required=False, allow_none=True,
                                  validate=validate.OneOf(["I", "II", "III", "IV", None]))
    dc_pue        = fields.Float(required=False, allow_none=True,
                                 validate=validate.Range(min=1.0, max=5.0))
    dc_it_load_mw = fields.Float(required=False, allow_none=True,
                                 validate=validate.Range(min=0.0))

    factory_process_type  = fields.String(required=False, allow_none=True,
                                          validate=validate.Length(max=80))
    factory_shift_pattern = fields.String(required=False, allow_none=True,
                                          validate=validate.Length(max=40))

    target_commissioning_date = fields.Date(required=False, allow_none=True)
    estimated_capex_inr_lakh  = fields.Float(required=False, allow_none=True,
                                             validate=validate.Range(min=0.0))
    project_id = fields.Integer(required=False, allow_none=True)


# =====================================================================
#  FEASIBILITY STUDY
# =====================================================================
class FeasibilityCheckSchema(Schema):
    id                  = fields.Integer(dump_only=True)
    study_id            = fields.Integer()
    substation_id       = fields.Integer()
    substation          = fields.Raw(allow_none=True)
    rank                = fields.Integer()
    score               = fields.Float()
    straight_distance_km= fields.Float()
    routed_distance_km  = fields.Float(allow_none=True)
    headroom_mva        = fields.Float(allow_none=True)
    headroom_ratio      = fields.Float(allow_none=True)
    voltage_drop_pct    = fields.Float(allow_none=True)
    estimated_losses_kw = fields.Float(allow_none=True)
    short_circuit_ok    = fields.Boolean(allow_none=True)
    verdict             = fields.String()
    reasons             = fields.String(allow_none=True)
    upgrade_needed      = fields.String(allow_none=True)


class FeasibilityStudySchema(Schema):
    id                  = fields.Integer(dump_only=True)
    facility_id         = fields.Integer()
    job_id              = fields.Integer(allow_none=True)
    search_radius_km    = fields.Float()
    max_voltage_drop_pct= fields.Float()
    min_headroom_factor = fields.Float()
    verdict             = fields.String()
    chosen_substation_id= fields.Integer(allow_none=True)
    summary             = fields.String(allow_none=True)
    recommendation      = fields.String(allow_none=True)
    estimated_cost_inr_lakh  = fields.Float(allow_none=True)
    estimated_lead_time_days = fields.Integer(allow_none=True)
    check_count         = fields.Integer(dump_only=True)
    checks              = fields.List(fields.Nested(FeasibilityCheckSchema), required=False)
    created_at          = fields.String(dump_only=True)
    completed_at        = fields.String(allow_none=True, dump_only=True)


class FeasibilityStudyCreateSchema(Schema):
    """POST /facilities/<id>/feasibility body."""
    search_radius_km     = fields.Float(load_default=15.0,
                                        validate=validate.Range(min=0.5, max=200.0))
    max_voltage_drop_pct = fields.Float(load_default=5.0,
                                        validate=validate.Range(min=0.1, max=30.0))
    min_headroom_factor  = fields.Float(load_default=1.2,
                                        validate=validate.Range(min=1.0, max=10.0))
