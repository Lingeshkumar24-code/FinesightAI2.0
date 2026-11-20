def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_login_issues_token(client):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "x"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_requires_credentials(client):
    resp = client.post("/api/v1/auth/login", json={"email": "", "password": ""})
    assert resp.status_code == 400


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_identity_with_valid_token(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["business_id"] == "demo-business-001"


def test_protected_endpoint_rejects_garbage_token(client):
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401
