"""LoadFlowService integration tests against pandapower IEEE cases."""
import pytest

pandapower = pytest.importorskip("pandapower")  # skip if not installed

from extension import db
from Models import (
    PowerNetwork, NetworkStatus, AnalysisJob,
    AnalysisType, AnalysisStatus,
)
from Services.pandapower_service import PandapowerService
from Services.load_flow_service   import LoadFlowService


@pytest.fixture
def case9_network(user, db_session):
    net = PowerNetwork(
        user_id=user.id, name="case9",
        base_mva=100.0, freq_hz=50.0,
        status=NetworkStatus.DRAFT,
    )
    db_session.add(net); db_session.commit()
    PandapowerService.load_template_into_db(net.id, "case9")
    return db.session.get(PowerNetwork, net.id)


def _make_job(net, user, **cfg):
    job = AnalysisJob(
        network_id=net.id, user_id=user.id,
        analysis_type=AnalysisType.LOAD_FLOW,
        status=AnalysisStatus.PENDING,
    )
    job.config = {"algorithm": "nr", "check_violations": True, **cfg}
    db.session.add(job); db.session.commit()
    return job


def test_load_flow_converges_on_case9(case9_network, user):
    job = _make_job(case9_network, user)
    result = LoadFlowService.run(job.id)
    db.session.refresh(job)
    assert job.status == AnalysisStatus.COMPLETED
    assert job.converged is True
    assert result["converged"] is True
    summary = job.results["summary"]
    assert summary["min_vm_pu"] is not None
    # All voltages within usual operating band
    assert 0.85 <= summary["min_vm_pu"] <= 1.15
    assert 0.85 <= summary["max_vm_pu"] <= 1.15


def test_load_flow_dc_runs(case9_network, user):
    job = _make_job(case9_network, user, algorithm="dc")
    LoadFlowService.run(job.id)
    db.session.refresh(job)
    assert job.status == AnalysisStatus.COMPLETED


def test_load_flow_invalid_algo_fails(case9_network, user):
    job = _make_job(case9_network, user)
    job.config = {**job.config, "algorithm": "spaceship"}
    db.session.commit()
    with pytest.raises(ValueError):
        LoadFlowService.run(job.id)
    db.session.refresh(job)
    # Service marks FAILED inside the try/except for runtime errors,
    # but ValueError is raised before status flips — accept either.
    assert job.status in (AnalysisStatus.PENDING, AnalysisStatus.FAILED,
                          AnalysisStatus.RUNNING)


def test_violations_recorded_on_overload(user, db_session):
    """Build a tiny overloaded network and confirm violations come back."""
    net = PowerNetwork(user_id=user.id, name="overload",
                       base_mva=100.0, freq_hz=50.0,
                       status=NetworkStatus.DRAFT)
    db_session.add(net); db_session.flush()

    from Models import Bus, Line, ExtGrid, Load
    b0 = Bus(network_id=net.id, pp_index=0, vn_kv=20.0)
    b1 = Bus(network_id=net.id, pp_index=1, vn_kv=20.0)
    db_session.add_all([b0, b1]); db_session.flush()
    db_session.add(ExtGrid(network_id=net.id, pp_index=0,
                           bus_id=b0.id, vm_pu=1.0))
    # Tiny conductor — easily overloaded
    db_session.add(Line(
        network_id=net.id, pp_index=0,
        from_bus_id=b0.id, to_bus_id=b1.id,
        length_km=20.0, r_ohm_per_km=0.5, x_ohm_per_km=0.4,
        c_nf_per_km=10.0, max_i_ka=0.1,
    ))
    db_session.add(Load(
        network_id=net.id, pp_index=0,
        bus_id=b1.id, p_mw=20.0, q_mvar=5.0,
    ))
    db_session.commit()

    job = _make_job(net, user)
    LoadFlowService.run(job.id)
    db.session.refresh(job)
    assert job.status == AnalysisStatus.COMPLETED
    # Expect at least one violation on the deliberately undersized line
    assert len(job.violations) > 0
