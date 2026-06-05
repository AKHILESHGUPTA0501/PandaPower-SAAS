"""Facility route tests."""


def test_create_facility_auto_size(client, auth_headers):
    res = client.post("/api/facilities/", headers=auth_headers, json={
        "name": "Big DC",
        "latitude": 22.5, "longitude": 88.3,
        "demand_mw": 25.0,
        "facility_type": "data_centre",
    })
    assert res.status_code == 201
    body = res.get_json()["data"]["facility"]
    # 25 MW falls into the LARGE bucket (10-50 MVA)
    assert body["size_class"] == "large"


def test_create_facility_validation(client, auth_headers):
    res = client.post("/api/facilities/", headers=auth_headers, json={
        "name": "x", "latitude": 22.5,
    })
    assert res.status_code == 400


def test_create_facility_bad_type(client, auth_headers):
    res = client.post("/api/facilities/", headers=auth_headers, json={
        "name": "x", "latitude": 22.5, "longitude": 88.3,
        "demand_mw": 1.0, "facility_type": "spaceship",
    })
    assert res.status_code == 400


def test_get_facility(client, auth_headers, sample_facility):
    res = client.get(f"/api/facilities/{sample_facility.id}",
                     headers=auth_headers)
    assert res.status_code == 200
    body = res.get_json()["data"]["facility"]
    assert body["id"] == sample_facility.id
    assert body["demand_mva"] > body["demand_mw"]


def test_other_user_cannot_get_facility(client, other_headers,
                                        sample_facility):
    res = client.get(f"/api/facilities/{sample_facility.id}",
                     headers=other_headers)
    assert res.status_code == 404


def test_update_facility_size_reclassifies(client, auth_headers,
                                           sample_facility):
    res = client.patch(f"/api/facilities/{sample_facility.id}",
                       headers=auth_headers,
                       json={"demand_mw": 75.0})
    assert res.status_code == 200
    assert res.get_json()["data"]["facility"]["size_class"] == "xlarge"


def test_delete_facility(client, auth_headers, sample_facility):
    res = client.delete(f"/api/facilities/{sample_facility.id}",
                        headers=auth_headers)
    assert res.status_code == 200


def test_nearby_substations_for_facility(client, auth_headers,
                                          sample_facility, sample_substation):
    res = client.get(
        f"/api/facilities/{sample_facility.id}/nearby-substations?radius_km=5",
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.get_json()["data"]
    # the sample substation is ~1km from the facility
    assert any(s["id"] == sample_substation.id for s in body["substations"])


def test_run_feasibility_creates_study(client, auth_headers,
                                       sample_facility):
    res = client.post(
        f"/api/facilities/{sample_facility.id}/feasibility",
        headers=auth_headers, json={"search_radius_km": 10.0},
    )
    assert res.status_code == 202
    body = res.get_json()["data"]["study"]
    assert body["facility_id"] == sample_facility.id
    assert body["search_radius_km"] == 10.0


def test_list_studies_starts_empty(client, auth_headers, sample_facility):
    res = client.get(f"/api/facilities/{sample_facility.id}/studies",
                     headers=auth_headers)
    assert res.status_code == 200
    assert res.get_json()["data"]["studies"] == []
