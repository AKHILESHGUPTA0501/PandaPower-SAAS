"""FeasibilityService unit tests."""
import json
import math
import pytest

from extension import db
from Models import (
    Substation, Facility, FacilityType, FacilitySize,
    FeasibilityStudy, FeasibilityVerdict,
)
from Services.feasibility_service import FeasibilityService


# ---------------------------------------------------------------------
#  Pure-math helpers
# ---------------------------------------------------------------------
def test_voltage_drop_zero_distance():
    drop = FeasibilityService._estimate_voltage_drop_pct(
        voltage_kv=33.0, length_km=0.0, demand_mva=5.0, pf=0.9,
    )
    assert drop == pytest.approx(0.0, abs=1e-9)


def test_voltage_drop_scales_with_length():
    a = FeasibilityService._estimate_voltage_drop_pct(33.0, 1.0, 5.0, 0.9)
    b = FeasibilityService._estimate_voltage_drop_pct(33.0, 10.0, 5.0, 0.9)
    assert b == pytest.approx(a * 10.0, rel=1e-6)


def test_voltage_drop_higher_voltage_lower_drop():
    low_v  = FeasibilityService._estimate_voltage_drop_pct(11.0,  5.0, 5.0, 0.9)
    high_v = FeasibilityService._estimate_voltage_drop_pct(132.0, 5.0, 5.0, 0.9)
    assert high_v < low_v


def test_voltage_drop_zero_voltage():
    drop = FeasibilityService._estimate_voltage_drop_pct(0.0, 5.0, 5.0, 0.9)
    assert drop == 100.0


def test_losses_positive():
    losses = FeasibilityService._estimate_losses_kw(33.0, 5.0, 5.0, 0.9)
    assert losses > 0


def test_losses_scale_with_demand_squared():
    a = FeasibilityService._estimate_losses_kw(33.0, 5.0, 5.0, 0.9)
    b = FeasibilityService._estimate_losses_kw(33.0, 5.0, 10.0, 0.9)
    # I scales linearly with MVA -> losses scale with MVA²
    assert b == pytest.approx(a * 4.0, rel=1e-6)


# ---------------------------------------------------------------------
#  Scoring
# ---------------------------------------------------------------------
def test_score_high_for_perfect_candidate():
    score, verdict = FeasibilityService._compute_score_and_verdict(
        headroom_ok=True, headroom_ratio=2.5,
        voltage_ok=True, v_drop_pct=1.0, max_drop_pct=5.0,
        sc_ok=True, distance_km=1.0, search_radius_km=15.0,
        upgrade_needed=[], data_complete=True,
    )
    assert score > 0.85
    assert verdict == FeasibilityVerdict.FEASIBLE


def test_score_zero_when_data_missing():
    score, verdict = FeasibilityService._compute_score_and_verdict(
        headroom_ok=None, headroom_ratio=None,
        voltage_ok=True, v_drop_pct=0.0, max_drop_pct=5.0,
        sc_ok=None, distance_km=1.0, search_radius_km=15.0,
        upgrade_needed=[], data_complete=False,
    )
    assert verdict == FeasibilityVerdict.INSUFFICIENT_DATA


def test_score_returns_not_feasible_when_no_capacity():
    score, verdict = FeasibilityService._compute_score_and_verdict(
        headroom_ok=False, headroom_ratio=0.3,
        voltage_ok=True, v_drop_pct=3.0, max_drop_pct=5.0,
        sc_ok=True, distance_km=1.0, search_radius_km=15.0,
        upgrade_needed=[], data_complete=True,
    )
    assert verdict == FeasibilityVerdict.NOT_FEASIBLE


def test_score_with_upgrade_path():
    score, verdict = FeasibilityService._compute_score_and_verdict(
        headroom_ok=False, headroom_ratio=0.9,
        voltage_ok=True, v_drop_pct=3.0, max_drop_pct=5.0,
        sc_ok=True, distance_km=1.0, search_radius_km=15.0,
        upgrade_needed=["Add transformer capacity"], data_complete=True,
    )
    assert verdict == FeasibilityVerdict.FEASIBLE_WITH_UPGRADE


# ---------------------------------------------------------------------
#  Cost / lead-time estimates
# ---------------------------------------------------------------------
def test_cost_lead_time_scale_with_upgrades():
    cost_a, lead_a = FeasibilityService._estimate_cost_and_lead_time(
        {"upgrade_needed": []}, distance_km=5.0, demand_mw=10.0,
    )
    cost_b, lead_b = FeasibilityService._estimate_cost_and_lead_time(
        {"upgrade_needed": ["Add transformer capacity",
                            "Larger conductor"]},
        distance_km=5.0, demand_mw=10.0,
    )
    assert cost_b > cost_a
    assert lead_b > lead_a


# ---------------------------------------------------------------------
#  Full run via DB
# ---------------------------------------------------------------------
@pytest.fixture
def feasibility_setup(user, db_session, admin_user):
    # Substation with enough headroom 1 km from facility
    sub = Substation(
        name="Local-Sub", latitude=22.580, longitude=88.360,
        primary_voltage_kv=33.0, transformer_capacity_mva=100.0,
        current_loading_percent=20.0, s_sc_max_mva=2000.0,
        is_active=True, is_public=True,
        uploaded_by_id=admin_user.id, data_source="manual", country="IN",
    )
    db_session.add(sub); db_session.flush()

    fac = Facility(
        user_id=user.id, name="Test fac",
        facility_type=FacilityType.FACTORY, size_class=FacilitySize.MEDIUM,
        latitude=22.582, longitude=88.362,
        demand_mw=5.0, power_factor=0.9, required_voltage_kv=33.0,
        country="IN",
    )
    db_session.add(fac); db_session.flush()

    study = FeasibilityStudy(facility_id=fac.id, search_radius_km=10.0)
    db_session.add(study); db_session.commit()
    return study, fac, sub


def test_feasibility_full_run_finds_substation(feasibility_setup):
    study, fac, sub = feasibility_setup
    summary = FeasibilityService.run(study.id)

    assert summary["candidate_count"] >= 1
    db.session.refresh(study)
    assert study.verdict == FeasibilityVerdict.FEASIBLE
    assert study.chosen_substation_id == sub.id
    assert study.summary is not None
    assert study.recommendation is not None


def test_feasibility_no_substations(user, db_session):
    fac = Facility(
        user_id=user.id, name="Lonely fac",
        facility_type=FacilityType.FACTORY, size_class=FacilitySize.SMALL,
        latitude=10.0, longitude=10.0,  # nowhere near anything
        demand_mw=1.0, power_factor=0.9, country="IN",
    )
    db_session.add(fac); db_session.flush()
    study = FeasibilityStudy(facility_id=fac.id, search_radius_km=5.0)
    db_session.add(study); db_session.commit()

    summary = FeasibilityService.run(study.id)
    db.session.refresh(study)
    assert summary["verdict"] == FeasibilityVerdict.NOT_FEASIBLE.value


def test_feasibility_check_rows_persisted(feasibility_setup):
    study, _, _ = feasibility_setup
    FeasibilityService.run(study.id)
    db.session.refresh(study)
    assert len(study.checks) >= 1
    # The reasons / upgrade_needed columns hold JSON-encoded lists
    check = study.checks[0]
    assert isinstance(json.loads(check.reasons or "[]"),         list)
    assert isinstance(json.loads(check.upgrade_needed or "[]"),  list)
