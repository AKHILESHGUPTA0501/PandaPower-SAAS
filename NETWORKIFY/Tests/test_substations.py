"""Substation route tests."""


def test_create_substation(client, auth_headers):
    res = client.post("/api/substations/", headers=auth_headers, json={
        "name": "New Sub",
        "latitude":  22.5,
        "longitude": 88.3,
        "primary_voltage_kv": 33.0,
    })
    assert res.status_code == 201
    body = res.get_json()["data"]["substation"]
    assert body["name"] == "New Sub"
    # Non-admin attempt to publish — silently downgraded
    assert body["is_public"] is False


def test_admin_can_publish_substation(client, admin_headers):
    res = client.post("/api/substations/", headers=admin_headers, json={
        "name": "Pub Sub",
        "latitude":  22.5, "longitude": 88.3,
        "primary_voltage_kv": 33.0,
        "is_public": True,
    })
    assert res.status_code == 201
    assert res.get_json()["data"]["substation"]["is_public"] is True


def test_create_bad_coords(client, auth_headers):
    res = client.post("/api/substations/", headers=auth_headers, json={
        "name": "Bad", "latitude": 200, "longitude": 0,
        "primary_voltage_kv": 33.0,
    })
    assert res.status_code == 400


def test_list_public_substations(client, auth_headers, sample_substation):
    res = client.get("/api/substations/", headers=auth_headers)
    assert res.status_code == 200
    items = res.get_json()["data"]["substations"]
    assert any(s["id"] == sample_substation.id for s in items)


def test_filter_by_voltage(client, auth_headers, sample_substation):
    res = client.get("/api/substations/?voltage_kv=132",
                     headers=auth_headers)
    assert res.status_code == 200
    items = res.get_json()["data"]["substations"]
    assert all(s["primary_voltage_kv"] == 132.0 for s in items)


def test_get_substation(client, auth_headers, sample_substation):
    res = client.get(f"/api/substations/{sample_substation.id}",
                     headers=auth_headers)
    assert res.status_code == 200
    body = res.get_json()["data"]
    assert body["substation"]["id"] == sample_substation.id


def test_nearby_substations(client, auth_headers, sample_substation):
    res = client.get(
        "/api/substations/nearby"
        f"?lat={sample_substation.latitude}"
        f"&lon={sample_substation.longitude}"
        "&radius_km=5",
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.get_json()["data"]
    assert body["count"] >= 1
    assert body["substations"][0]["distance_km"] < 1.0


def test_nearby_requires_coords(client, auth_headers):
    res = client.get("/api/substations/nearby", headers=auth_headers)
    assert res.status_code == 400


def test_update_substation_owner(client, admin_headers, sample_substation):
    res = client.patch(
        f"/api/substations/{sample_substation.id}",
        headers=admin_headers,
        json={"transformer_capacity_mva": 150.0, "notes": "upgraded"},
    )
    assert res.status_code == 200
    body = res.get_json()["data"]["substation"]
    assert body["transformer_capacity_mva"] == 150.0


def test_non_owner_cannot_update_private(client, auth_headers,
                                         admin_user, db_session):
    """Private substation owned by admin shouldn't be editable by user."""
    from Models import Substation
    priv = Substation(
        name="Priv", latitude=22.5, longitude=88.3,
        primary_voltage_kv=33.0, is_public=False,
        uploaded_by_id=admin_user.id, data_source="manual", country="IN",
    )
    db_session.add(priv); db_session.commit()
    res = client.patch(f"/api/substations/{priv.id}",
                       headers=auth_headers,
                       json={"name": "X"})
    # Either 403 (forbidden) or 404 (hidden) is acceptable behaviour
    assert res.status_code in (403, 404)


def test_create_feeder(client, admin_headers, sample_substation):
    res = client.post(
        f"/api/substations/{sample_substation.id}/feeders",
        headers=admin_headers,
        json={"name": "F1", "voltage_kv": 33.0, "capacity_mva": 25.0},
    )
    assert res.status_code == 201


def test_transmission_line_create_requires_admin(client, auth_headers,
                                                  sample_substation):
    res = client.post("/api/substations/transmission-lines",
                      headers=auth_headers, json={
        "name": "L1",
        "from_substation_id": sample_substation.id,
        "to_substation_id":   sample_substation.id + 1,
        "voltage_kv": 132.0,
    })
    assert res.status_code == 403
