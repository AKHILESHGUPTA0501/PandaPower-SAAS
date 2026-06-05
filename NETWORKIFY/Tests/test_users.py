"""User route tests."""


def test_list_users_requires_admin(client, auth_headers):
    res = client.get("/api/users/", headers=auth_headers)
    assert res.status_code == 403


def test_list_users_as_admin(client, admin_headers, user):
    res = client.get("/api/users/", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    # at least the admin + the user
    assert len(body["data"]["users"]) >= 2


def test_get_self(client, auth_headers, user):
    res = client.get(f"/api/users/{user.id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.get_json()["data"]["user"]["id"] == user.id


def test_get_other_user_forbidden(client, auth_headers, another_user):
    res = client.get(f"/api/users/{another_user.id}", headers=auth_headers)
    assert res.status_code == 403


def test_admin_can_get_any_user(client, admin_headers, user):
    res = client.get(f"/api/users/{user.id}", headers=admin_headers)
    assert res.status_code == 200


def test_self_update_limited_fields(client, auth_headers, user):
    res = client.patch(f"/api/users/{user.id}",
                       headers=auth_headers,
                       json={"full_name": "Self Updated",
                             "role":      "admin"})
    assert res.status_code == 200
    body = res.get_json()["data"]["user"]
    assert body["full_name"] == "Self Updated"
    # Non-admin cannot promote themselves
    assert body["role"] != "admin"


def test_admin_can_promote_user(client, admin_headers, user):
    res = client.patch(f"/api/users/{user.id}",
                       headers=admin_headers,
                       json={"role": "engineer"})
    assert res.status_code == 200
    assert res.get_json()["data"]["user"]["role"] == "engineer"


def test_admin_deactivate_user(client, admin_headers, user):
    res = client.delete(f"/api/users/{user.id}", headers=admin_headers)
    assert res.status_code == 200


def test_cannot_deactivate_last_admin(client, admin_headers, admin_user):
    res = client.delete(f"/api/users/{admin_user.id}", headers=admin_headers)
    assert res.status_code == 400


def test_activate_user(client, admin_headers, user, db_session):
    user.is_active = False
    db_session.commit()
    res = client.post(f"/api/users/{user.id}/activate",
                      headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()["data"]["user"]["is_active"] is True
