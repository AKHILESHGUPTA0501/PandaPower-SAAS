"""FactoryPresets unit tests."""
import pytest

from Services.factory_presets import FactoryPresets


def test_get_known_preset():
    p = FactoryPresets.get("factory", "medium")
    assert p is not None
    assert p["demand_mw"] > 0
    assert 0 < p["power_factor"] <= 1


def test_get_unknown_returns_none():
    assert FactoryPresets.get("warehouse", "xlarge") is None
    assert FactoryPresets.get("not_a_type", "small") is None


def test_list_presets_nonempty():
    presets = FactoryPresets.list_presets()
    assert len(presets) > 0
    assert all("facility_type" in p and "size" in p for p in presets)


def test_data_centre_presets_have_dc_fields():
    p = FactoryPresets.get("data_centre", "large")
    assert p["dc_tier"] in {"I", "II", "III", "IV"}
    assert p["dc_pue"] > 1.0
    assert p["dc_it_load_mw"] > 0


def test_load_profile_lengths():
    p = FactoryPresets.get_load_profile("factory_24x7")
    assert len(p) == 24
    assert all(0 <= v <= 1 for v in p)


def test_load_profile_steps_repeat():
    p48 = FactoryPresets.get_load_profile("office", steps=48)
    p24 = FactoryPresets.get_load_profile("office", steps=24)
    assert len(p48) == 48
    assert p48[:24] == p24


def test_load_profile_solar_zero_at_night():
    p = FactoryPresets.get_load_profile("solar_pv")
    # Indexes 0-4 and 21-23 should be ~0
    assert all(p[i] == 0.0 for i in [0, 1, 2, 3, 4, 21, 22, 23])
    # Peak around midday
    assert max(p[10:14]) >= 0.95


def test_unknown_profile_raises():
    with pytest.raises(ValueError):
        FactoryPresets.get_load_profile("imaginary")


def test_list_profiles_includes_basics():
    profiles = FactoryPresets.list_profiles()
    for name in ("factory_24x7", "datacentre_steady", "solar_pv", "office"):
        assert name in profiles


@pytest.mark.parametrize("demand_mw,expected", [
    (0.1,   "small"),
    (1.0,   "small"),
    (5.0,   "medium"),
    (10.0,  "medium"),
    (25.0,  "large"),
    (50.0,  "large"),
    (100.0, "xlarge"),
])
def test_size_classification(demand_mw, expected):
    assert FactoryPresets.classify_size(demand_mw) == expected
