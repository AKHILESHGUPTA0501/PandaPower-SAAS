"""
PowerNetwork and pandapower element schemas.

Each element type has three flavours:
  - <Element>Schema        — output (all fields, dump_only)
  - <Element>CreateSchema  — input for POST (required + optional fields)
  - <Element>UpdateSchema  — input for PATCH (all optional)
"""
from marshmallow import Schema, fields, validate

from Models import NetworkStatus


# =====================================================================
#  PowerNetwork
# =====================================================================
class PowerNetworkSchema(Schema):
    id              = fields.Integer(dump_only=True)
    user_id         = fields.Integer(dump_only=True)
    project_id      = fields.Integer(allow_none=True)
    name            = fields.String(required=True, validate=validate.Length(min=1, max=120))
    description     = fields.String(allow_none=True)
    status          = fields.String()
    base_mva        = fields.Float()
    freq_hz         = fields.Float()
    is_template     = fields.Boolean()
    template_name   = fields.String(allow_none=True)
    is_public       = fields.Boolean()
    bus_count         = fields.Integer(dump_only=True)
    line_count        = fields.Integer(dump_only=True)
    transformer_count = fields.Integer(dump_only=True)
    load_count        = fields.Integer(dump_only=True)
    gen_count         = fields.Integer(dump_only=True)
    created_at      = fields.String(dump_only=True)
    updated_at      = fields.String(dump_only=True)


class PowerNetworkCreateSchema(Schema):
    name        = fields.String(required=True, validate=validate.Length(min=1, max=120))
    description = fields.String(required=False, allow_none=True)
    base_mva    = fields.Float(load_default=100.0,
                            validate=validate.Range(min=0.001))
    freq_hz     = fields.Float(load_default=50.0,
                            validate=validate.OneOf([50.0, 60.0]))
    project_id  = fields.Integer(required=False, allow_none=True)


class PowerNetworkUpdateSchema(Schema):
    name        = fields.String(required=False, validate=validate.Length(min=1, max=120))
    description = fields.String(required=False, allow_none=True)
    status      = fields.String(
        required=False,
        validate=validate.OneOf([s.value for s in NetworkStatus]),
    )
    base_mva    = fields.Float(required=False, validate=validate.Range(min=0.001))
    freq_hz     = fields.Float(required=False, validate=validate.OneOf([50.0, 60.0]))
    is_public   = fields.Boolean(required=False)
    project_id  = fields.Integer(required=False, allow_none=True)


class NetworkTemplateSchema(Schema):
    """POST /networks/<id>/from-template body."""
    template = fields.String(
        required=True,
        validate=validate.OneOf([
            "case4gs", "case6ww", "case9", "case14",
            "case30", "case39", "case57", "case118",
            "mv_oberrhein",
        ]),
    )


# =====================================================================
#  BUS
# =====================================================================
class BusSchema(Schema):
    id         = fields.Integer(dump_only=True)
    pp_index   = fields.Integer()
    name       = fields.String(allow_none=True)
    vn_kv      = fields.Float()
    bus_type   = fields.String()
    in_service = fields.Boolean()
    max_vm_pu  = fields.Float()
    min_vm_pu  = fields.Float()
    geo_x      = fields.Float(allow_none=True)
    geo_y      = fields.Float(allow_none=True)
    zone       = fields.String(allow_none=True)


class BusCreateSchema(Schema):
    pp_index   = fields.Integer(required=False)
    name       = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    vn_kv      = fields.Float(required=True, validate=validate.Range(min=0.1, max=1500.0))
    bus_type   = fields.String(load_default="b", validate=validate.OneOf(["b", "n", "m"]))
    in_service = fields.Boolean(load_default=True)
    max_vm_pu  = fields.Float(load_default=1.1, validate=validate.Range(min=0.5, max=2.0))
    min_vm_pu  = fields.Float(load_default=0.9, validate=validate.Range(min=0.5, max=2.0))
    geo_x      = fields.Float(required=False, allow_none=True)
    geo_y      = fields.Float(required=False, allow_none=True)
    zone       = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))


class BusUpdateSchema(Schema):
    name       = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    vn_kv      = fields.Float(required=False, validate=validate.Range(min=0.1, max=1500.0))
    bus_type   = fields.String(required=False, validate=validate.OneOf(["b", "n", "m"]))
    in_service = fields.Boolean(required=False)
    max_vm_pu  = fields.Float(required=False, validate=validate.Range(min=0.5, max=2.0))
    min_vm_pu  = fields.Float(required=False, validate=validate.Range(min=0.5, max=2.0))
    geo_x      = fields.Float(required=False, allow_none=True)
    geo_y      = fields.Float(required=False, allow_none=True)
    zone       = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))


# =====================================================================
#  LINE
# =====================================================================
class LineSchema(Schema):
    id          = fields.Integer(dump_only=True)
    pp_index    = fields.Integer()
    name        = fields.String(allow_none=True)
    from_bus_id = fields.Integer()
    to_bus_id   = fields.Integer()
    length_km   = fields.Float()
    std_type    = fields.String(allow_none=True)
    r_ohm_per_km= fields.Float(allow_none=True)
    x_ohm_per_km= fields.Float(allow_none=True)
    c_nf_per_km = fields.Float(allow_none=True)
    max_i_ka    = fields.Float(allow_none=True)
    parallel    = fields.Integer()
    df          = fields.Float()
    in_service  = fields.Boolean()


class LineCreateSchema(Schema):
    pp_index    = fields.Integer(required=False)
    name        = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    from_bus_id = fields.Integer(required=True)
    to_bus_id   = fields.Integer(required=True)
    length_km   = fields.Float(required=True, validate=validate.Range(min=0.001, max=10000.0))
    std_type    = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    r_ohm_per_km= fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    x_ohm_per_km= fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    c_nf_per_km = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    max_i_ka    = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    parallel    = fields.Integer(load_default=1, validate=validate.Range(min=1, max=99))
    df          = fields.Float(load_default=1.0, validate=validate.Range(min=0.01, max=1.0))
    in_service  = fields.Boolean(load_default=True)


class LineUpdateSchema(Schema):
    name        = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    from_bus_id = fields.Integer(required=False)
    to_bus_id   = fields.Integer(required=False)
    length_km   = fields.Float(required=False, validate=validate.Range(min=0.001, max=10000.0))
    std_type    = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    r_ohm_per_km= fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    x_ohm_per_km= fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    c_nf_per_km = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    max_i_ka    = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    parallel    = fields.Integer(required=False, validate=validate.Range(min=1, max=99))
    df          = fields.Float(required=False, validate=validate.Range(min=0.01, max=1.0))
    in_service  = fields.Boolean(required=False)


# =====================================================================
#  TRANSFORMER
# =====================================================================
class TransformerSchema(Schema):
    id           = fields.Integer(dump_only=True)
    pp_index     = fields.Integer()
    name         = fields.String(allow_none=True)
    hv_bus_id    = fields.Integer()
    lv_bus_id    = fields.Integer()
    sn_mva       = fields.Float()
    vn_hv_kv     = fields.Float()
    vn_lv_kv     = fields.Float()
    vk_percent   = fields.Float(allow_none=True)
    vkr_percent  = fields.Float(allow_none=True)
    pfe_kw       = fields.Float(allow_none=True)
    i0_percent   = fields.Float(allow_none=True)
    tap_pos      = fields.Integer()
    std_type     = fields.String(allow_none=True)
    in_service   = fields.Boolean()


class TransformerCreateSchema(Schema):
    pp_index     = fields.Integer(required=False)
    name         = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    hv_bus_id    = fields.Integer(required=True)
    lv_bus_id    = fields.Integer(required=True)
    sn_mva       = fields.Float(required=True, validate=validate.Range(min=0.001, max=10000.0))
    vn_hv_kv     = fields.Float(required=True, validate=validate.Range(min=0.1, max=1500.0))
    vn_lv_kv     = fields.Float(required=True, validate=validate.Range(min=0.1, max=1500.0))
    vk_percent   = fields.Float(required=False, allow_none=True,
                                validate=validate.Range(min=0.0, max=100.0))
    vkr_percent  = fields.Float(required=False, allow_none=True,
                                validate=validate.Range(min=0.0, max=100.0))
    pfe_kw       = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    i0_percent   = fields.Float(required=False, allow_none=True,
                                validate=validate.Range(min=0.0, max=100.0))
    shift_degree = fields.Float(load_default=0.0)
    std_type     = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    tap_pos      = fields.Integer(load_default=0)
    parallel     = fields.Integer(load_default=1, validate=validate.Range(min=1, max=99))
    in_service   = fields.Boolean(load_default=True)


class TransformerUpdateSchema(Schema):
    name         = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    hv_bus_id    = fields.Integer(required=False)
    lv_bus_id    = fields.Integer(required=False)
    sn_mva       = fields.Float(required=False, validate=validate.Range(min=0.001, max=10000.0))
    vn_hv_kv     = fields.Float(required=False, validate=validate.Range(min=0.1, max=1500.0))
    vn_lv_kv     = fields.Float(required=False, validate=validate.Range(min=0.1, max=1500.0))
    vk_percent   = fields.Float(required=False, allow_none=True,
                                validate=validate.Range(min=0.0, max=100.0))
    vkr_percent  = fields.Float(required=False, allow_none=True,
                                validate=validate.Range(min=0.0, max=100.0))
    pfe_kw       = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    i0_percent   = fields.Float(required=False, allow_none=True,
                                validate=validate.Range(min=0.0, max=100.0))
    shift_degree = fields.Float(required=False)
    std_type     = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    tap_pos      = fields.Integer(required=False)
    parallel     = fields.Integer(required=False, validate=validate.Range(min=1, max=99))
    in_service   = fields.Boolean(required=False)


# =====================================================================
#  LOAD
# =====================================================================
class LoadSchema(Schema):
    id         = fields.Integer(dump_only=True)
    pp_index   = fields.Integer()
    name       = fields.String(allow_none=True)
    bus_id     = fields.Integer()
    p_mw       = fields.Float()
    q_mvar     = fields.Float()
    sn_mva     = fields.Float(allow_none=True)
    scaling    = fields.Float()
    load_type  = fields.String(allow_none=True)
    in_service = fields.Boolean()


class LoadCreateSchema(Schema):
    pp_index        = fields.Integer(required=False)
    name            = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id          = fields.Integer(required=True)
    p_mw            = fields.Float(load_default=0.0)
    q_mvar          = fields.Float(load_default=0.0)
    sn_mva          = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    const_z_percent = fields.Float(load_default=0.0, validate=validate.Range(min=0.0, max=100.0))
    const_i_percent = fields.Float(load_default=0.0, validate=validate.Range(min=0.0, max=100.0))
    scaling         = fields.Float(load_default=1.0, validate=validate.Range(min=0.0, max=100.0))
    load_type       = fields.String(required=False, allow_none=True, validate=validate.Length(max=40))
    in_service      = fields.Boolean(load_default=True)


class LoadUpdateSchema(Schema):
    name            = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id          = fields.Integer(required=False)
    p_mw            = fields.Float(required=False)
    q_mvar          = fields.Float(required=False)
    sn_mva          = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    const_z_percent = fields.Float(required=False, validate=validate.Range(min=0.0, max=100.0))
    const_i_percent = fields.Float(required=False, validate=validate.Range(min=0.0, max=100.0))
    scaling         = fields.Float(required=False, validate=validate.Range(min=0.0, max=100.0))
    load_type       = fields.String(required=False, allow_none=True, validate=validate.Length(max=40))
    in_service      = fields.Boolean(required=False)


# =====================================================================
#  GENERATOR
# =====================================================================
class GeneratorSchema(Schema):
    id         = fields.Integer(dump_only=True)
    pp_index   = fields.Integer()
    name       = fields.String(allow_none=True)
    bus_id     = fields.Integer()
    p_mw       = fields.Float()
    vm_pu      = fields.Float()
    sn_mva     = fields.Float(allow_none=True)
    slack      = fields.Boolean()
    gen_type   = fields.String(allow_none=True)
    in_service = fields.Boolean()


class GeneratorCreateSchema(Schema):
    pp_index   = fields.Integer(required=False)
    name       = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id     = fields.Integer(required=True)
    p_mw       = fields.Float(load_default=0.0)
    vm_pu      = fields.Float(load_default=1.0, validate=validate.Range(min=0.5, max=2.0))
    sn_mva     = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    min_q_mvar = fields.Float(required=False, allow_none=True)
    max_q_mvar = fields.Float(required=False, allow_none=True)
    min_p_mw   = fields.Float(required=False, allow_none=True)
    max_p_mw   = fields.Float(required=False, allow_none=True)
    slack      = fields.Boolean(load_default=False)
    gen_type   = fields.String(required=False, allow_none=True, validate=validate.Length(max=40))
    in_service = fields.Boolean(load_default=True)


class GeneratorUpdateSchema(Schema):
    name       = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id     = fields.Integer(required=False)
    p_mw       = fields.Float(required=False)
    vm_pu      = fields.Float(required=False, validate=validate.Range(min=0.5, max=2.0))
    sn_mva     = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    min_q_mvar = fields.Float(required=False, allow_none=True)
    max_q_mvar = fields.Float(required=False, allow_none=True)
    min_p_mw   = fields.Float(required=False, allow_none=True)
    max_p_mw   = fields.Float(required=False, allow_none=True)
    slack      = fields.Boolean(required=False)
    gen_type   = fields.String(required=False, allow_none=True, validate=validate.Length(max=40))
    in_service = fields.Boolean(required=False)


# =====================================================================
#  EXT GRID
# =====================================================================
class ExtGridSchema(Schema):
    id           = fields.Integer(dump_only=True)
    pp_index     = fields.Integer()
    name         = fields.String(allow_none=True)
    bus_id       = fields.Integer()
    vm_pu        = fields.Float()
    va_degree    = fields.Float()
    s_sc_max_mva = fields.Float(allow_none=True)
    in_service   = fields.Boolean()


class ExtGridCreateSchema(Schema):
    pp_index     = fields.Integer(required=False)
    name         = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id       = fields.Integer(required=True)
    vm_pu        = fields.Float(load_default=1.0, validate=validate.Range(min=0.5, max=2.0))
    va_degree    = fields.Float(load_default=0.0)
    s_sc_max_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    s_sc_min_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    rx_max       = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    rx_min       = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    in_service   = fields.Boolean(load_default=True)


class ExtGridUpdateSchema(Schema):
    name         = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id       = fields.Integer(required=False)
    vm_pu        = fields.Float(required=False, validate=validate.Range(min=0.5, max=2.0))
    va_degree    = fields.Float(required=False)
    s_sc_max_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    s_sc_min_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    rx_max       = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    rx_min       = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    in_service   = fields.Boolean(required=False)


# =====================================================================
#  SWITCH
# =====================================================================
class SwitchSchema(Schema):
    id               = fields.Integer(dump_only=True)
    pp_index         = fields.Integer()
    name             = fields.String(allow_none=True)
    bus_id           = fields.Integer()
    element_type     = fields.String()
    element_pp_index = fields.Integer()
    closed           = fields.Boolean()
    switch_type      = fields.String(allow_none=True)


class SwitchCreateSchema(Schema):
    pp_index         = fields.Integer(required=False)
    name             = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id           = fields.Integer(required=True)
    element_type     = fields.String(required=True, validate=validate.OneOf(["l", "t", "b"]))
    element_pp_index = fields.Integer(required=True)
    closed           = fields.Boolean(load_default=True)
    switch_type      = fields.String(required=False, allow_none=True, validate=validate.Length(max=20))
    z_ohm            = fields.Float(load_default=0.0, validate=validate.Range(min=0.0))


class SwitchUpdateSchema(Schema):
    name             = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id           = fields.Integer(required=False)
    element_type     = fields.String(required=False, validate=validate.OneOf(["l", "t", "b"]))
    element_pp_index = fields.Integer(required=False)
    closed           = fields.Boolean(required=False)
    switch_type      = fields.String(required=False, allow_none=True, validate=validate.Length(max=20))
    z_ohm            = fields.Float(required=False, validate=validate.Range(min=0.0))


# =====================================================================
#  SHUNT
# =====================================================================
class ShuntSchema(Schema):
    id         = fields.Integer(dump_only=True)
    pp_index   = fields.Integer()
    name       = fields.String(allow_none=True)
    bus_id     = fields.Integer()
    p_mw       = fields.Float()
    q_mvar     = fields.Float()
    vn_kv      = fields.Float()
    step       = fields.Integer()
    in_service = fields.Boolean()


class ShuntCreateSchema(Schema):
    pp_index   = fields.Integer(required=False)
    name       = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id     = fields.Integer(required=True)
    p_mw       = fields.Float(load_default=0.0)
    q_mvar     = fields.Float(load_default=0.0)
    vn_kv      = fields.Float(required=True, validate=validate.Range(min=0.1, max=1500.0))
    step       = fields.Integer(load_default=1, validate=validate.Range(min=0))
    max_step   = fields.Integer(load_default=1, validate=validate.Range(min=1))
    in_service = fields.Boolean(load_default=True)


class ShuntUpdateSchema(Schema):
    name       = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    bus_id     = fields.Integer(required=False)
    p_mw       = fields.Float(required=False)
    q_mvar     = fields.Float(required=False)
    vn_kv      = fields.Float(required=False, validate=validate.Range(min=0.1, max=1500.0))
    step       = fields.Integer(required=False, validate=validate.Range(min=0))
    max_step   = fields.Integer(required=False, validate=validate.Range(min=1))
    in_service = fields.Boolean(required=False)
