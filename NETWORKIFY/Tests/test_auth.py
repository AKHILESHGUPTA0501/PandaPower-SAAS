"""Auth route tests."""
import pytest


def test_register_success(client):
    res = client.post("/api/auth/register", json={
        "username": "newuser",
        "email":    "new@example.com",
        "password": "Password1!",
    })
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["user"]["username"] == "newuser"
    assert "access_token" in body["data"]


def test_register_missing_fields(client):
    res = client.post("/api/auth/register", json={"email": "x@y.com"})
    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_register_weak_password(client):
    res = client.post("/api/auth/register", json={
        "username": "weak", "email": "w@x.com", "password": "short",
    })
    assert res.status_code == 400


def test_register_duplicate(client, user):
    res = client.post("/api/auth/register", json={
        "username": user.username,
        "email":    "alt@example.com",
        "password": "Password1!",
    })
    assert res.status_code == 409


def test_login_success(client, user):
    res = client.post("/api/auth/login", json={
        "email":    user.email,
        "password": "Password1!",
    })
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert "access_token" in body["data"]


def test_login_wrong_password(client, user):
    res = client.post("/api/auth/login", json={
        "email": user.email, "password": "WrongPass1!",
    })
    assert res.status_code == 401
    assert res.get_json()["success"] is False


def test_login_unknown_user(client):
    res = client.post("/api/auth/login", json={
        "email": "nope@example.com", "password": "Password1!",
    })
    assert res.status_code == 401


def test_login_inactive_user(client, user, db_session):
    user.is_active = False
    db_session.commit()
    res = client.post("/api/auth/login", json={
        "email": user.email, "password": "Password1!",
    })
    assert res.status_code == 403


def test_me_requires_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_with_token(client, auth_headers, user):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.get_json()["data"]["user"]["id"] == user.id


def test_change_password_flow(client, auth_headers, user):
    # Wrong current password
    bad = client.post("/api/auth/change-password",
                      headers=auth_headers,
                      json={"current_password": "Wrong1!",
                            "new_password":     "NewPass1!"})
    assert bad.status_code == 401

    # Correct change
    ok = client.post("/api/auth/change-password",
                     headers=auth_headers,
                     json={"current_password": "Password1!",
                           "new_password":     "Brand1New!"})
    assert ok.status_code == 200

    # Old password no longer works
    failed = client.post("/api/auth/login", json={
        "email": user.email, "password": "Password1!",
    })
    assert failed.status_code == 401


def test_logout_returns_ok(client, auth_headers):
    res = client.post("/api/auth/logout", headers=auth_headers)
    assert res.status_code == 200
    assert res.get_json()["success"] is True


def test_forgot_password_unknown_email_still_ok(client):
    # Always returns 200 to avoid email enumeration
    res = client.post("/api/auth/forgot-password",
                      json={"email": "ghost@nowhere.com"})
    assert res.status_code == 200


def test_update_me_profile(client, auth_headers):
    res = client.patch("/api/auth/me", headers=auth_headers,
                       json={"full_name": "Test Person",
                             "company":   "Acme Consulting"})
    assert res.status_code == 200
    user_data = res.get_json()["data"]["user"]
    assert user_data["full_name"] == "Test Person"
    assert user_data["company"]   == "Acme Consulting"
