
"""GeoService unit tests."""
import math
import pytest

from Services.geo_service import GeoService


def test_haversine_zero_distance():
    assert GeoService.haversine_km(22.5, 88.3, 22.5, 88.3) == \
        pytest.approx(0.0, abs=1e-9)


def test_haversine_known_distance():
    # Kolkata <-> Delhi ~ 1305 km
    d = GeoService.haversine_km(22.5726, 88.3639, 28.6139, 77.2090)
    assert 1280 <= d <= 1340


def test_haversine_symmetric():
    a = GeoService.haversine_km(0.0, 0.0, 10.0, 10.0)
    b = GeoService.haversine_km(10.0, 10.0, 0.0, 0.0)
    assert a == pytest.approx(b)


def test_bounding_box_size():
    min_lat, max_lat, min_lon, max_lon = GeoService.bounding_box(
        22.5, 88.3, radius_km=10.0,
    )
    # Latitude span ≈ 2 * 10/111 deg
    assert (max_lat - min_lat) == pytest.approx(2 * 10.0 / 111.0, rel=1e-6)
    assert min_lon < 88.3 < max_lon
    assert min_lat < 22.5 < max_lat


def test_estimated_route_distance_applies_detour():
    straight = GeoService.haversine_km(22.5, 88.3, 22.6, 88.4)
    routed   = GeoService.estimated_route_distance_km(22.5, 88.3, 22.6, 88.4,
                                                      detour_factor=1.3)
    assert routed == pytest.approx(straight * 1.3, rel=1e-6)


def test_find_within_radius_filters_by_distance(admin_user, sample_substation,
                                                db_session):
    from Models import Substation
    far_sub = Substation(
        name="Far", latitude=10.0, longitude=10.0,
        primary_voltage_kv=132.0, is_public=True, is_active=True,
        uploaded_by_id=admin_user.id, data_source="manual", country="IN",
    )
    db_session.add(far_sub); db_session.commit()

    hits = GeoService.find_substations_within_radius(
        lat=sample_substation.latitude,
        lon=sample_substation.longitude,
        radius_km=5,
    )
    sub_ids = {s.id for s, _ in hits}
    assert sample_substation.id in sub_ids
    assert far_sub.id not in sub_ids


def test_find_within_radius_voltage_filter(admin_user, sample_substation,
                                           db_session):
    from Models import Substation
    low_v = Substation(
        name="LowV",
        latitude=sample_substation.latitude  + 0.001,
        longitude=sample_substation.longitude + 0.001,
        primary_voltage_kv=11.0,
        is_public=True, is_active=True,
        uploaded_by_id=admin_user.id, data_source="manual", country="IN",
    )
    db_session.add(low_v); db_session.commit()

    hits = GeoService.find_substations_within_radius(
        lat=sample_substation.latitude,
        lon=sample_substation.longitude,
        radius_km=2, min_voltage_kv=66.0,
    )
    voltages = {s.primary_voltage_kv for s, _ in hits}
    assert all(v >= 66.0 for v in voltages)


def test_find_within_radius_sorted_by_distance(admin_user, db_session):
    from Models import Substation
    base = (22.5, 88.3)
    s1 = Substation(name="A", latitude=22.5,    longitude=88.31,
                    primary_voltage_kv=33.0, is_active=True, is_public=True,
                    uploaded_by_id=admin_user.id, data_source="manual",
                    country="IN")
    s2 = Substation(name="B", latitude=22.51,   longitude=88.32,
                    primary_voltage_kv=33.0, is_active=True, is_public=True,
                    uploaded_by_id=admin_user.id, data_source="manual",
                    country="IN")
    s3 = Substation(name="C", latitude=22.52,   longitude=88.33,
                    primary_voltage_kv=33.0, is_active=True, is_public=True,
                    uploaded_by_id=admin_user.id, data_source="manual",
                    country="IN")
    db_session.add_all([s1, s2, s3]); db_session.commit()

    hits = GeoService.find_substations_within_radius(*base, radius_km=20)
    distances = [d for _, d in hits]
    assert distances == sorted(distances)
