"""Marshmallow schema validation tests."""
import pytest
from marshmallow import ValidationError

from Schemas import (
    RegisterSchema, LoginSchema,
    PowerNetworkCreateSchema,
    BusCreateSchema, LineCreateSchema,
    SubstationCreateSchema, NearbySearchSchema, OSMImportSchema,
    FacilityCreateSchema,
    LoadFlowRequestSchema, ShortCircuitRequestSchema,
    TimeSeriesRequestSchema, ContingencyRequestSchema,
)


# ---------------------------------------------------------------------
#  Auth
# ---------------------------------------------------------------------
def test_register_valid():
    data = RegisterSchema().load({
        "username": "u", "email": "u@x.com", "password": "Password1!",
    })
    assert data["email"] == "u@x.com"


def test_register_short_password():
    with pytest.raises(ValidationError):
        RegisterSchema().load({
            "username": "u", "email": "u@x.com", "password": "short",
        })


def test_register_password_no_letter():
    with pytest.raises(ValidationError):
        RegisterSchema().load({
            "username": "u", "email": "u@x.com", "password": "12345678",
        })


def test_login_requires_email_password():
    with pytest.raises(ValidationError):
        LoginSchema().load({"email": "u@x.com"})


# ---------------------------------------------------------------------
#  Network elements
# ---------------------------------------------------------------------
def test_network_create_defaults():
    data = PowerNetworkCreateSchema().load({"name": "X"})
    assert data["base_mva"] == 100.0
    assert data["freq_hz"]  == 50.0


def test_network_create_bad_frequency():
    with pytest.raises(ValidationError):
        PowerNetworkCreateSchema().load({"name": "X", "freq_hz": 25})


def test_bus_create_requires_vn_kv():
    with pytest.raises(ValidationError):
        BusCreateSchema().load({})


def test_bus_create_vn_kv_out_of_range():
    with pytest.raises(ValidationError):
        BusCreateSchema().load({"vn_kv": 9999.0})


def test_line_create_requires_buses():
    with pytest.raises(ValidationError):
        LineCreateSchema().load({"length_km": 1.0})


def test_line_create_valid():
    data = LineCreateSchema().load({
        "from_bus_id": 1, "to_bus_id": 2, "length_km": 5.0,
    })
    assert data["parallel"] == 1
    assert data["df"]       == 1.0


# ---------------------------------------------------------------------
#  Substation
# ---------------------------------------------------------------------
def test_substation_create_valid():
    data = SubstationCreateSchema().load({
        "name": "S", "latitude": 22.5, "longitude": 88.3,
        "primary_voltage_kv": 33.0,
    })
    assert data["country"] == "IN"


def test_substation_bad_lat():
    with pytest.raises(ValidationError):
        SubstationCreateSchema().load({
            "name": "S", "latitude": 999, "longitude": 88.3,
            "primary_voltage_kv": 33.0,
        })


def test_nearby_search_requires_coords():
    with pytest.raises(ValidationError):
        NearbySearchSchema().load({})


def test_osm_import_box_must_be_consistent():
    with pytest.raises(ValidationError):
        OSMImportSchema().load({
            "south": 23.0, "west": 88.0, "north": 22.0, "east": 89.0,
        })


def test_osm_import_box_too_large():
    with pytest.raises(ValidationError):
        OSMImportSchema().load({
            "south": 10.0, "west": 70.0, "north": 30.0, "east": 90.0,
        })


# ---------------------------------------------------------------------
#  Facility
# ---------------------------------------------------------------------
def test_facility_valid():
    data = FacilityCreateSchema().load({
        "name": "Fac", "latitude": 22.5, "longitude": 88.3,
        "demand_mw": 5.0,
    })
    assert data["facility_type"] == "factory"


def test_facility_bad_pf():
    with pytest.raises(ValidationError):
        FacilityCreateSchema().load({
            "name": "Fac", "latitude": 22.5, "longitude": 88.3,
            "demand_mw": 5.0, "power_factor": 1.5,
        })


def test_facility_bad_dc_tier():
    with pytest.raises(ValidationError):
        FacilityCreateSchema().load({
            "name": "Fac", "latitude": 22.5, "longitude": 88.3,
            "demand_mw": 5.0, "dc_tier": "V",
        })


# ---------------------------------------------------------------------
#  Analysis requests
# ---------------------------------------------------------------------
def test_load_flow_request_defaults():
    data = LoadFlowRequestSchema().load({"network_id": 1})
    assert data["algorithm"]     == "nr"
    assert data["max_iteration"] == 50


def test_load_flow_bad_algo():
    with pytest.raises(ValidationError):
        LoadFlowRequestSchema().load({
            "network_id": 1, "algorithm": "magic",
        })


def test_short_circuit_request_defaults():
    data = ShortCircuitRequestSchema().load({"network_id": 1})
    assert data["fault_type"] == "3ph"
    assert data["case"]       == "max"


def test_short_circuit_bad_fault():
    with pytest.raises(ValidationError):
        ShortCircuitRequestSchema().load({
            "network_id": 1, "fault_type": "nuclear",
        })


def test_time_series_requires_steps():
    with pytest.raises(ValidationError):
        TimeSeriesRequestSchema().load({"network_id": 1})


def test_time_series_steps_capped():
    with pytest.raises(ValidationError):
        TimeSeriesRequestSchema().load({"network_id": 1, "steps": 99999})


def test_contingency_default_elements_empty():
    data = ContingencyRequestSchema().load({"network_id": 1})
    assert data["elements"] == []
    assert data["check_loading_pct"] == 100.0
