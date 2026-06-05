"""PowerNetwork route tests."""


def test_create_network(client, auth_headers):
    res = client.post("/api/networks/", headers=auth_headers,
                      json={"name": "My Net", "base_mva": 100.0})
    assert res.status_code == 201
    body = res.get_json()
    assert body["data"]["network"]["name"] == "My Net"


def test_create_network_missing_name(client, auth_headers):
    res = client.post("/api/networks/", headers=auth_headers, json={})
    assert res.status_code == 400


def test_list_networks(client, auth_headers, empty_network):
    res = client.get("/api/networks/", headers=auth_headers)
    assert res.status_code == 200
    nets = res.get_json()["data"]["networks"]
    assert any(n["id"] == empty_network.id for n in nets)


def test_get_network_with_elements(client, auth_headers, sample_network):
    res = client.get(f"/api/networks/{sample_network.id}",
                     headers=auth_headers)
    assert res.status_code == 200
    body = res.get_json()["data"]
    assert body["network"]["id"] == sample_network.id
    assert len(body["buses"]) == 2
    assert len(body["lines"]) == 1
    assert len(body["loads"]) == 1


def test_get_other_user_network_not_found(client, other_headers,
                                          empty_network):
    res = client.get(f"/api/networks/{empty_network.id}",
                     headers=other_headers)
    assert res.status_code == 404


def test_update_network(client, auth_headers, empty_network):
    res = client.patch(f"/api/networks/{empty_network.id}",
                       headers=auth_headers,
                       json={"name": "Renamed", "is_public": True})
    assert res.status_code == 200
    body = res.get_json()["data"]["network"]
    assert body["name"]      == "Renamed"
    assert body["is_public"] is True


def test_update_network_bad_status(client, auth_headers, empty_network):
    res = client.patch(f"/api/networks/{empty_network.id}",
                       headers=auth_headers,
                       json={"status": "not_a_status"})
    assert res.status_code == 400


def test_delete_network(client, auth_headers, empty_network):
    res = client.delete(f"/api/networks/{empty_network.id}",
                        headers=auth_headers)
    assert res.status_code == 200
    res = client.get(f"/api/networks/{empty_network.id}",
                     headers=auth_headers)
    assert res.status_code == 404


# ---- Element CRUD --------------------------------------------------
def test_create_bus(client, auth_headers, empty_network):
    res = client.post(f"/api/networks/{empty_network.id}/buses",
                      headers=auth_headers,
                      json={"vn_kv": 11.0, "name": "MyBus"})
    assert res.status_code == 201
    el = res.get_json()["data"]["element"]
    assert el["vn_kv"] == 11.0
    assert el["pp_index"] == 0


def test_create_bus_validation(client, auth_headers, empty_network):
    res = client.post(f"/api/networks/{empty_network.id}/buses",
                      headers=auth_headers, json={})
    assert res.status_code == 400


def test_list_buses(client, auth_headers, sample_network):
    res = client.get(f"/api/networks/{sample_network.id}/buses",
                     headers=auth_headers)
    assert res.status_code == 200
    assert len(res.get_json()["data"]["buses"]) == 2


def test_update_bus(client, auth_headers, sample_network):
    bus = sample_network.buses[0]
    res = client.patch(
        f"/api/networks/{sample_network.id}/buses/{bus.id}",
        headers=auth_headers,
        json={"name": "Renamed-Bus", "vn_kv": 132.0},
    )
    assert res.status_code == 200
    body = res.get_json()["data"]["element"]
    assert body["name"]  == "Renamed-Bus"
    assert body["vn_kv"] == 132.0


def test_delete_load(client, auth_headers, sample_network):
    load = sample_network.loads[0]
    res = client.delete(
        f"/api/networks/{sample_network.id}/loads/{load.id}",
        headers=auth_headers,
    )
    assert res.status_code == 200


def test_share_network(client, auth_headers, empty_network):
    res = client.post(f"/api/networks/{empty_network.id}/share",
                      headers=auth_headers)
    assert res.status_code == 200
    body = res.get_json()["data"]
    assert body["share_token"]
    assert body["share_path"].startswith("/api/networks/shared/")


def test_template_request_invalid_name(client, auth_headers, empty_network):
    res = client.post(
        f"/api/networks/{empty_network.id}/from-template",
        headers=auth_headers,
        json={"template": "not_a_real_one"},
    )
    assert res.status_code == 400
