"""
Substation, feeder, transmission line, geo-search, and OSM import schemas.
"""
from marshmallow import Schema, fields, validate, validates_schema, ValidationError


# =====================================================================
#  SUBSTATION
# =====================================================================
class SubstationSchema(Schema):
    id                       = fields.Integer(dump_only=True)
    name                     = fields.String()
    code                     = fields.String(allow_none=True)
    owner_utility            = fields.String(allow_none=True)
    region                   = fields.String(allow_none=True)
    city                     = fields.String(allow_none=True)
    country                  = fields.String()
    latitude                 = fields.Float()
    longitude                = fields.Float()
    primary_voltage_kv       = fields.Float()
    secondary_voltage_kv     = fields.Float(allow_none=True)
    substation_type          = fields.String(allow_none=True)
    transformer_capacity_mva = fields.Float(allow_none=True)
    current_loading_percent  = fields.Float(allow_none=True)
    available_capacity_mva   = fields.Float(allow_none=True)
    headroom_mva             = fields.Float(allow_none=True, dump_only=True)
    is_active                = fields.Boolean()
    data_source              = fields.String(allow_none=True)
    is_public                = fields.Boolean()
    created_at               = fields.String(dump_only=True)


class SubstationCreateSchema(Schema):
    name          = fields.String(required=True, validate=validate.Length(min=1, max=160))
    code          = fields.String(required=False, allow_none=True, validate=validate.Length(max=60))
    owner_utility = fields.String(required=False, allow_none=True, validate=validate.Length(max=120))
    region        = fields.String(required=False, allow_none=True, validate=validate.Length(max=80))
    city          = fields.String(required=False, allow_none=True, validate=validate.Length(max=80))
    country       = fields.String(load_default="IN", validate=validate.Length(max=60))
    latitude      = fields.Float(required=True, validate=validate.Range(min=-90.0,  max=90.0))
    longitude     = fields.Float(required=True, validate=validate.Range(min=-180.0, max=180.0))
    elevation_m   = fields.Float(required=False, allow_none=True)
    primary_voltage_kv  = fields.Float(required=True, validate=validate.Range(min=0.1, max=1500.0))
    secondary_voltage_kv= fields.Float(required=False, allow_none=True,
                                    validate=validate.Range(min=0.1, max=1500.0))
    substation_type     = fields.String(
        required=False, allow_none=True,
        validate=validate.OneOf(["transmission", "distribution", "switching", None]),
    )
    transformer_capacity_mva = fields.Float(required=False, allow_none=True,
                                            validate=validate.Range(min=0.0))
    transformer_count        = fields.Integer(load_default=1, validate=validate.Range(min=1))
    current_loading_percent  = fields.Float(required=False, allow_none=True,
                                            validate=validate.Range(min=0.0, max=200.0))
    available_capacity_mva   = fields.Float(required=False, allow_none=True,
                                            validate=validate.Range(min=0.0))
    s_sc_max_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    s_sc_min_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    x_r_ratio    = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    is_active    = fields.Boolean(load_default=True)
    data_source  = fields.String(load_default="manual",
                                validate=validate.OneOf(["manual", "csv_upload", "osm"]))
    notes        = fields.String(required=False, allow_none=True)
    project_id   = fields.Integer(required=False, allow_none=True)
    is_public    = fields.Boolean(load_default=False)


class SubstationUpdateSchema(Schema):
    name          = fields.String(required=False, validate=validate.Length(min=1, max=160))
    code          = fields.String(required=False, allow_none=True, validate=validate.Length(max=60))
    owner_utility = fields.String(required=False, allow_none=True, validate=validate.Length(max=120))
    region        = fields.String(required=False, allow_none=True, validate=validate.Length(max=80))
    city          = fields.String(required=False, allow_none=True, validate=validate.Length(max=80))
    country       = fields.String(required=False, validate=validate.Length(max=60))
    latitude      = fields.Float(required=False, validate=validate.Range(min=-90.0,  max=90.0))
    longitude     = fields.Float(required=False, validate=validate.Range(min=-180.0, max=180.0))
    elevation_m   = fields.Float(required=False, allow_none=True)
    primary_voltage_kv  = fields.Float(required=False, validate=validate.Range(min=0.1, max=1500.0))
    secondary_voltage_kv= fields.Float(required=False, allow_none=True,
                                        validate=validate.Range(min=0.1, max=1500.0))
    substation_type     = fields.String(required=False, allow_none=True)
    transformer_capacity_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    transformer_count        = fields.Integer(required=False, validate=validate.Range(min=1))
    current_loading_percent  = fields.Float(required=False, allow_none=True,
                                            validate=validate.Range(min=0.0, max=200.0))
    available_capacity_mva   = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    s_sc_max_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    s_sc_min_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    x_r_ratio    = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    is_active    = fields.Boolean(required=False)
    notes        = fields.String(required=False, allow_none=True)
    is_public    = fields.Boolean(required=False)
    project_id   = fields.Integer(required=False, allow_none=True)


# =====================================================================
#  FEEDER
# =====================================================================
class SubstationFeederSchema(Schema):
    id               = fields.Integer(dump_only=True)
    substation_id    = fields.Integer()
    name             = fields.String()
    voltage_kv       = fields.Float()
    capacity_mva     = fields.Float(allow_none=True)
    current_load_mva = fields.Float(allow_none=True)
    available_mva    = fields.Float(allow_none=True, dump_only=True)
    conductor_type   = fields.String(allow_none=True)
    length_km        = fields.Float(allow_none=True)
    is_active        = fields.Boolean()


class SubstationFeederCreateSchema(Schema):
    name             = fields.String(required=True, validate=validate.Length(min=1, max=120))
    voltage_kv       = fields.Float(required=True, validate=validate.Range(min=0.1, max=1500.0))
    capacity_mva     = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    current_load_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    conductor_type   = fields.String(required=False, allow_none=True, validate=validate.Length(max=60))
    length_km        = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    is_active        = fields.Boolean(load_default=True)


class SubstationFeederUpdateSchema(Schema):
    name             = fields.String(required=False, validate=validate.Length(min=1, max=120))
    voltage_kv       = fields.Float(required=False, validate=validate.Range(min=0.1, max=1500.0))
    capacity_mva     = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    current_load_mva = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    conductor_type   = fields.String(required=False, allow_none=True, validate=validate.Length(max=60))
    length_km        = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    is_active        = fields.Boolean(required=False)


# =====================================================================
#  TRANSMISSION LINE
# =====================================================================
class TransmissionLineSchema(Schema):
    id                 = fields.Integer(dump_only=True)
    name               = fields.String()
    from_substation_id = fields.Integer()
    to_substation_id   = fields.Integer()
    voltage_kv         = fields.Float()
    length_km          = fields.Float(allow_none=True)
    capacity_mva       = fields.Float(allow_none=True)
    conductor_type     = fields.String(allow_none=True)
    num_circuits       = fields.Integer()
    is_underground     = fields.Boolean()
    is_active          = fields.Boolean()


class TransmissionLineCreateSchema(Schema):
    name               = fields.String(required=True, validate=validate.Length(min=1, max=160))
    from_substation_id = fields.Integer(required=True)
    to_substation_id   = fields.Integer(required=True)
    voltage_kv         = fields.Float(required=True, validate=validate.Range(min=0.1, max=1500.0))
    length_km          = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    capacity_mva       = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0.0))
    conductor_type     = fields.String(required=False, allow_none=True, validate=validate.Length(max=60))
    num_circuits       = fields.Integer(load_default=1, validate=validate.Range(min=1, max=10))
    is_underground     = fields.Boolean(load_default=False)
    is_active          = fields.Boolean(load_default=True)

    @validates_schema
    def _ends_differ(self, data, **kwargs):
        if data.get("from_substation_id") == data.get("to_substation_id"):
            raise ValidationError("from and to substations must differ",
                                field_name="to_substation_id")


# =====================================================================
#  GEO / OSM
# =====================================================================
class NearbySearchSchema(Schema):
    """GET /substations/nearby query params."""
    lat            = fields.Float(required=True, validate=validate.Range(min=-90.0,  max=90.0))
    lon            = fields.Float(required=True, validate=validate.Range(min=-180.0, max=180.0))
    radius_km      = fields.Float(load_default=25.0, validate=validate.Range(min=0.1, max=500.0))
    limit          = fields.Integer(load_default=20, validate=validate.Range(min=1, max=200))
    min_voltage_kv = fields.Float(required=False, allow_none=True,
                                validate=validate.Range(min=0.1, max=1500.0))


class OSMImportSchema(Schema):
    """POST /substations/import-osm body."""
    south = fields.Float(required=True, validate=validate.Range(min=-90.0,  max=90.0))
    west  = fields.Float(required=True, validate=validate.Range(min=-180.0, max=180.0))
    north = fields.Float(required=True, validate=validate.Range(min=-90.0,  max=90.0))
    east  = fields.Float(required=True, validate=validate.Range(min=-180.0, max=180.0))

    @validates_schema
    def _box_consistent(self, data, **kwargs):
        if data["south"] >= data["north"]:
            raise ValidationError("south must be less than north", field_name="south")
        if data["west"]  >= data["east"]:
            raise ValidationError("west must be less than east",   field_name="west")
        # Reasonable size cap (~5 deg) to protect the Overpass API
        if (data["north"] - data["south"]) > 5 or (data["east"] - data["west"]) > 5:
            raise ValidationError("Bounding box too large (>5°). Split into smaller boxes.")
