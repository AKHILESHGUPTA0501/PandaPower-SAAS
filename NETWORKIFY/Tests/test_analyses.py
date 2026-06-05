"""Analysis route tests — verify dispatch only, not pandapower internals."""


def test_load_flow_requires_network(client, auth_headers):
    res = client.post("/api/analyses/load-flow",
                      headers=auth_headers, json={})
    assert res.status_code == 400


def test_load_flow_bad_network(client, auth_headers):
    res = client.post("/api/analyses/load-flow",
                      headers=auth_headers,
                      json={"network_id": 99999})
    assert res.status_code == 404


def test_load_flow_dispatch(client, auth_headers, empty_network):
    res = client.post("/api/analyses/load-flow",
                      headers=auth_headers,
                      json={"network_id": empty_network.id})
    assert res.status_code == 202
    job = res.get_json()["data"]["job"]
    assert job["analysis_type"] == "load_flow"
    assert job["status"]        == "pending"


def test_load_flow_invalid_algorithm(client, auth_headers, empty_network):
    res = client.post("/api/analyses/load-flow",
                      headers=auth_headers,
                      json={"network_id": empty_network.id,
                            "algorithm":  "magic"})
    assert res.status_code == 400


def test_short_circuit_dispatch(client, auth_headers, empty_network):
    res = client.post("/api/analyses/short-circuit",
                      headers=auth_headers,
                      json={"network_id": empty_network.id,
                            "fault_type": "3ph"})
    assert res.status_code == 202


def test_short_circuit_invalid_fault(client, auth_headers, empty_network):
    res = client.post("/api/analyses/short-circuit",
                      headers=auth_headers,
                      json={"network_id": empty_network.id,
                            "fault_type": "xyz"})
    assert res.status_code == 400


def test_contingency_dispatch(client, auth_headers, empty_network):
    res = client.post("/api/analyses/contingency",
                      headers=auth_headers,
                      json={"network_id": empty_network.id})
    assert res.status_code == 202


def test_opf_dispatch(client, auth_headers, empty_network):
    res = client.post("/api/analyses/opf",
                      headers=auth_headers,
                      json={"network_id": empty_network.id})
    assert res.status_code == 202


def test_time_series_requires_steps(client, auth_headers, empty_network):
    res = client.post("/api/analyses/time-series",
                      headers=auth_headers,
                      json={"network_id": empty_network.id})
    assert res.status_code == 400


def test_time_series_dispatch(client, auth_headers, empty_network):
    res = client.post("/api/analyses/time-series",
                      headers=auth_headers,
                      json={"network_id": empty_network.id, "steps": 24})
    assert res.status_code == 202


def test_time_series_steps_out_of_range(client, auth_headers, empty_network):
    res = client.post("/api/analyses/time-series",
                      headers=auth_headers,
                      json={"network_id": empty_network.id, "steps": 100000})
    assert res.status_code == 400


def test_list_jobs(client, auth_headers, empty_network):
    client.post("/api/analyses/load-flow", headers=auth_headers,
                json={"network_id": empty_network.id})
    res = client.get("/api/analyses/", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.get_json()["data"]["jobs"]) >= 1


def test_get_job_violations_empty(client, auth_headers, empty_network):
    create = client.post("/api/analyses/load-flow",
                         headers=auth_headers,
                         json={"network_id": empty_network.id})
    job_id = create.get_json()["data"]["job"]["id"]
    res = client.get(f"/api/analyses/{job_id}/violations",
                     headers=auth_headers)
    assert res.status_code == 200
    assert res.get_json()["data"]["violations"] == []


def test_cancel_pending_job(client, auth_headers, empty_network):
    create = client.post("/api/analyses/load-flow",
                         headers=auth_headers,
                         json={"network_id": empty_network.id})
    job_id = create.get_json()["data"]["job"]["id"]
    res = client.post(f"/api/analyses/{job_id}/cancel",
                      headers=auth_headers)
    assert res.status_code == 200
    assert res.get_json()["data"]["job"]["status"] == "cancelled"


def test_other_user_cannot_see_job(client, auth_headers, other_headers,
                                    empty_network):
    create = client.post("/api/analyses/load-flow",
                         headers=auth_headers,
                         json={"network_id": empty_network.id})
    job_id = create.get_json()["data"]["job"]["id"]
    res = client.get(f"/api/analyses/{job_id}", headers=other_headers)
    assert res.status_code == 404
