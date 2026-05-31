"""
Subscription, plan, and usage-quota schemas.
"""
from marshmallow import Schema, fields, validate

from Models import PlanTier, SubscriptionStatus


# =====================================================================
#  PLAN
# =====================================================================
class _PlanLimitsSchema(Schema):
    max_networks           = fields.Integer(allow_none=True)
    max_buses_per_network  = fields.Integer(allow_none=True)
    max_analyses_per_month = fields.Integer(allow_none=True)
    max_reports_per_month  = fields.Integer(allow_none=True)
    max_facilities         = fields.Integer(allow_none=True)
    max_org_members        = fields.Integer(allow_none=True)


class _PlanFeaturesSchema(Schema):
    contingency      = fields.Boolean()
    opf              = fields.Boolean()
    timeseries       = fields.Boolean()
    pdf_branding     = fields.Boolean()
    api_access       = fields.Boolean()
    priority_compute = fields.Boolean()


class PlanSchema(Schema):
    id                  = fields.Integer(dump_only=True)
    tier                = fields.String()
    name                = fields.String()
    description         = fields.String(allow_none=True)
    price_inr_per_month = fields.Float(allow_none=True)
    price_inr_per_year  = fields.Float(allow_none=True)
    limits              = fields.Nested(_PlanLimitsSchema)
    features            = fields.Nested(_PlanFeaturesSchema)
    is_active           = fields.Boolean()


class PlanCreateSchema(Schema):
    tier        = fields.String(
        required=True,
        validate=validate.OneOf([t.value for t in PlanTier]),
    )
    name        = fields.String(required=True, validate=validate.Length(min=1, max=80))
    description = fields.String(required=False, allow_none=True)

    price_inr_per_month = fields.Float(required=False, allow_none=True,validate=validate.Range(min=0.0))
    price_inr_per_year  = fields.Float(required=False, allow_none=True,validate=validate.Range(min=0.0))

    max_networks           = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_buses_per_network  = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_analyses_per_month = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_reports_per_month  = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_facilities         = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_org_members        = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))

    allows_contingency      = fields.Boolean(load_default=False)
    allows_opf              = fields.Boolean(load_default=False)
    allows_timeseries       = fields.Boolean(load_default=False)
    allows_pdf_branding     = fields.Boolean(load_default=False)
    allows_api_access       = fields.Boolean(load_default=False)
    allows_priority_compute = fields.Boolean(load_default=False)

    is_active   = fields.Boolean(load_default=True)


class PlanUpdateSchema(Schema):
    name        = fields.String(required=False, validate=validate.Length(min=1, max=80))
    description = fields.String(required=False, allow_none=True)

    price_inr_per_month = fields.Float(required=False, allow_none=True,validate=validate.Range(min=0.0))
    price_inr_per_year  = fields.Float(required=False, allow_none=True,validate=validate.Range(min=0.0))

    max_networks           = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_buses_per_network  = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_analyses_per_month = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_reports_per_month  = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_facilities         = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))
    max_org_members        = fields.Integer(required=False, allow_none=True,
                                            validate=validate.Range(min=0))

    allows_contingency      = fields.Boolean(required=False)
    allows_opf              = fields.Boolean(required=False)
    allows_timeseries       = fields.Boolean(required=False)
    allows_pdf_branding     = fields.Boolean(required=False)
    allows_api_access       = fields.Boolean(required=False)
    allows_priority_compute = fields.Boolean(required=False)

    is_active   = fields.Boolean(required=False)


# =====================================================================
#  SUBSCRIPTION
# =====================================================================
class SubscriptionSchema(Schema):
    id                   = fields.Integer(dump_only=True)
    user_id              = fields.Integer(allow_none=True)
    org_id               = fields.Integer(allow_none=True)
    plan_id              = fields.Integer()
    plan                 = fields.Nested(PlanSchema, allow_none=True)
    status               = fields.String()
    started_at           = fields.String(allow_none=True)
    current_period_start = fields.String(allow_none=True)
    current_period_end   = fields.String(allow_none=True)
    trial_ends_at        = fields.String(allow_none=True)


# =====================================================================
#  USAGE QUOTA
# =====================================================================
class UsageQuotaSchema(Schema):
    id                       = fields.Integer(dump_only=True)
    user_id                  = fields.Integer()
    org_id                   = fields.Integer(allow_none=True)
    period_start             = fields.String()
    period_end               = fields.String()
    analyses_used            = fields.Integer()
    reports_used             = fields.Integer()
    feasibility_studies_used = fields.Integer()
    api_calls_used           = fields.Integer()
