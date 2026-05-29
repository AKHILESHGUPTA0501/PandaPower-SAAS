"""
Schemas package for PowerSys SaaS.

Marshmallow schemas for request validation and response serialisation.
Each schema mirrors a Model but is decoupled — input validation is
strict, output is what the frontend should see (no password_hash, etc.).

Usage in routes:
    from Schemas import RegisterSchema, NetworkSchema

    @auth_bp.post("/register")
    def register():
        schema = RegisterSchema()
        try:
            data = schema.load(request.get_json() or {})
        except ValidationError as e:
            return fail("Validation failed", 400, errors=e.messages)
        ...
"""
from .auth_schema import (
    RegisterSchema,
    LoginSchema,
    ChangePasswordSchema,
    ForgotPasswordSchema,
    ResetPasswordSchema,
    UserSchema,
    UserUpdateSchema,
)
from .network_schema import (
    PowerNetworkSchema,
    PowerNetworkCreateSchema,
    PowerNetworkUpdateSchema,
    BusSchema, BusCreateSchema, BusUpdateSchema,
    LineSchema, LineCreateSchema, LineUpdateSchema,
    TransformerSchema, TransformerCreateSchema, TransformerUpdateSchema,
    LoadSchema, LoadCreateSchema, LoadUpdateSchema,
    GeneratorSchema, GeneratorCreateSchema, GeneratorUpdateSchema,
    ExtGridSchema, ExtGridCreateSchema, ExtGridUpdateSchema,
    SwitchSchema, SwitchCreateSchema, SwitchUpdateSchema,
    ShuntSchema, ShuntCreateSchema, ShuntUpdateSchema,
    NetworkTemplateSchema,
)
from .substation_schema import (
    SubstationSchema,
    SubstationCreateSchema,
    SubstationUpdateSchema,
    SubstationFeederSchema,
    SubstationFeederCreateSchema,
    SubstationFeederUpdateSchema,
    TransmissionLineSchema,
    TransmissionLineCreateSchema,
    NearbySearchSchema,
    OSMImportSchema,
)
from .facility_schema import (
    FacilitySchema,
    FacilityCreateSchema,
    FacilityUpdateSchema,
    FeasibilityStudySchema,
    FeasibilityStudyCreateSchema,
    FeasibilityCheckSchema,
)
from .analysis_schema import (
    AnalysisJobSchema,
    LoadFlowRequestSchema,
    ShortCircuitRequestSchema,
    ContingencyRequestSchema,
    OPFRequestSchema,
    TimeSeriesRequestSchema,
    ViolationSchema,
    FaultResultSchema,
    ContingencyResultSchema,
    TimeSeriesResultSchema,
    ReportSchema,
    ReportCreateSchema,
)
from .organization_schema import (
    OrganizationSchema,
    OrganizationCreateSchema,
    OrganizationUpdateSchema,
    OrganizationMemberSchema,
    OrganizationMemberInviteSchema,
)
from .subscription_schema import (
    PlanSchema,
    PlanCreateSchema,
    PlanUpdateSchema,
    SubscriptionSchema,
    UsageQuotaSchema,
)
from .common_schema import (
    PaginationSchema,
    PaginationQuerySchema,
    ApiResponseSchema,
    ErrorResponseSchema,
)


__all__ = [
    # auth / user
    "RegisterSchema", "LoginSchema", "ChangePasswordSchema",
    "ForgotPasswordSchema", "ResetPasswordSchema",
    "UserSchema", "UserUpdateSchema",
    # network
    "PowerNetworkSchema", "PowerNetworkCreateSchema", "PowerNetworkUpdateSchema",
    "BusSchema", "BusCreateSchema", "BusUpdateSchema",
    "LineSchema", "LineCreateSchema", "LineUpdateSchema",
    "TransformerSchema", "TransformerCreateSchema", "TransformerUpdateSchema",
    "LoadSchema", "LoadCreateSchema", "LoadUpdateSchema",
    "GeneratorSchema", "GeneratorCreateSchema", "GeneratorUpdateSchema",
    "ExtGridSchema", "ExtGridCreateSchema", "ExtGridUpdateSchema",
    "SwitchSchema", "SwitchCreateSchema", "SwitchUpdateSchema",
    "ShuntSchema", "ShuntCreateSchema", "ShuntUpdateSchema",
    "NetworkTemplateSchema",
    # substation
    "SubstationSchema", "SubstationCreateSchema", "SubstationUpdateSchema",
    "SubstationFeederSchema", "SubstationFeederCreateSchema",
    "SubstationFeederUpdateSchema",
    "TransmissionLineSchema", "TransmissionLineCreateSchema",
    "NearbySearchSchema", "OSMImportSchema",
    # facility
    "FacilitySchema", "FacilityCreateSchema", "FacilityUpdateSchema",
    "FeasibilityStudySchema", "FeasibilityStudyCreateSchema",
    "FeasibilityCheckSchema",
    # analysis
    "AnalysisJobSchema",
    "LoadFlowRequestSchema", "ShortCircuitRequestSchema",
    "ContingencyRequestSchema", "OPFRequestSchema",
    "TimeSeriesRequestSchema",
    "ViolationSchema", "FaultResultSchema",
    "ContingencyResultSchema", "TimeSeriesResultSchema",
    "ReportSchema", "ReportCreateSchema",
    # organization
    "OrganizationSchema", "OrganizationCreateSchema", "OrganizationUpdateSchema",
    "OrganizationMemberSchema", "OrganizationMemberInviteSchema",
    # subscription
    "PlanSchema", "PlanCreateSchema", "PlanUpdateSchema",
    "SubscriptionSchema", "UsageQuotaSchema",
    # common
    "PaginationSchema", "PaginationQuerySchema",
    "ApiResponseSchema", "ErrorResponseSchema",
]
