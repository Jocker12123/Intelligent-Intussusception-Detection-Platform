def test_get_settings(client, auth_headers):
    resp = client.get("/api/settings", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_doctor_cannot_update_settings(client, auth_headers):
    resp = client.put(
        "/api/settings",
        json={"settings": [{"key": "theme", "value": "modern"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_admin_can_update_settings(client, admin_headers):
    resp = client.put(
        "/api/settings",
        json={"settings": [{"key": "theme", "value": "modern"}]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
