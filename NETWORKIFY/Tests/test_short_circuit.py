"""ShortCircuitService integration tests."""
import pytest

pandapower = pytest.importorskip("pandapower")
pytest.importorskip("pandapower.shortcircuit")

from extension import db
from Models import (
    PowerNetwork, NetworkStatus, AnalysisJob,
    AnalysisType, AnalysisStatus,
)
from Services.pandapower_service   import PandapowerService
from Services.short_circuit_service import ShortCircuitService


@pytest.fixture
def case9_with_sc_data(user, db_session):
    net = PowerNetwork(user_id=user.id, name="case9_sc",
                       base_mva=100.0, freq_hz=50.0,
                       status=NetworkStatus.DRAFT)
    db_session.add(net); db_session.commit()
    PandapowerService.load_template_into_db(net.id, "case9")

    # Ensure ext_grid has SC contribution data
    net_row = db.session.get(PowerNetwork, net.id)
    for eg in net_row.ext_grids:
        eg.s_sc_max_mva = 5000.0
        eg.s_sc_min_mva = 2000.0
        eg.rx_max       = 0.1
        eg.rx_min       = 0.1
    db.session.commit()
    return net_row


def _make_sc_job(net, user, **cfg):
    job = AnalysisJob(
        network_id=net.id, user_id=user.id,
        analysis_type=AnalysisType.SHORT_CIRCUIT,
        status=AnalysisStatus.PENDING,
    )
    job.config = {"fault_type": "3ph", "case": "max", **cfg}
    db.session.add(job); db.session.commit()
    return job


def test_sc_three_phase_runs(case9_with_sc_data, user):
    job = _make_sc_job(case9_with_sc_data, user)
    ShortCircuitService.run(job.id)
    db.session.refresh(job)
    assert job.status == AnalysisStatus.COMPLETED
    assert len(job.fault_results) > 0
    # Every bus should have a positive ikss
    for fr in job.fault_results:
        if fr.ikss_ka is not None:
            assert fr.ikss_ka > 0


def test_sc_invalid_fault_type(case9_with_sc_data, user):
    job = _make_sc_job(case9_with_sc_data, user)
    job.config = {**job.config, "fault_type": "nuclear"}
    db.session.commit()
    with pytest.raises(ValueError):
        ShortCircuitService.run(job.id)


def test_sc_specific_buses(case9_with_sc_data, user):
    job = _make_sc_job(case9_with_sc_data, user, fault_buses=[0, 1])
    ShortCircuitService.run(job.id)
    db.session.refresh(job)
    assert job.status == AnalysisStatus.COMPLETED
    bus_indices = {fr.fault_bus_pp_index for fr in job.fault_results}
    assert {0, 1}.issubset(bus_indices)
