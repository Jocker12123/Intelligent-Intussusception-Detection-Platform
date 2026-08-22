def test_create_patient(client, auth_headers):
    resp = client.post("/api/patients", json={
        "name": "Child A", "gender": "Male", "age": 24, "medical_record_no": "M001"
    }, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Child A"


def test_list_patients(client, auth_headers):
    client.post("/api/patients", json={"name": "P1", "gender": "Male", "age": 12}, headers=auth_headers)
    client.post("/api/patients", json={"name": "P2", "gender": "Female", "age": 6}, headers=auth_headers)
    resp = client.get("/api/patients", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_search_patients(client, auth_headers):
    client.post("/api/patients", json={"name": "Zhang Wei", "gender": "Male", "age": 24}, headers=auth_headers)
    client.post("/api/patients", json={"name": "Li Ming", "gender": "Female", "age": 6}, headers=auth_headers)
    resp = client.get("/api/patients?search=Zhang", headers=auth_headers)
    assert resp.json()["total"] == 1


def test_get_patient_not_found(client, auth_headers):
    resp = client.get("/api/patients/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_patient(client, auth_headers):
    create = client.post("/api/patients", json={"name": "P4", "gender": "Male", "age": 12}, headers=auth_headers)
    pid = create.json()["id"]
    resp = client.put(f"/api/patients/{pid}", json={"name": "Updated"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


def test_delete_patient(client, auth_headers):
    create = client.post("/api/patients", json={"name": "P5", "gender": "Female", "age": 3}, headers=auth_headers)
    pid = create.json()["id"]
    resp = client.delete(f"/api/patients/{pid}", headers=auth_headers)
    assert resp.status_code == 204
    get_resp = client.get(f"/api/patients/{pid}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_doctor_cannot_edit_others_patient(client, auth_headers, second_doctor_headers):
    """医生不能编辑别的医生录入的患者。"""
    create = client.post("/api/patients", json={"name": "Owner", "gender": "Male", "age": 12}, headers=auth_headers)
    pid = create.json()["id"]
    resp = client.put(f"/api/patients/{pid}", json={"name": "Hacked"}, headers=second_doctor_headers)
    assert resp.status_code == 403


def test_doctor_cannot_delete_others_patient(client, auth_headers, second_doctor_headers):
    """医生不能删除别的医生录入的患者。"""
    create = client.post("/api/patients", json={"name": "Owner", "gender": "Male", "age": 12}, headers=auth_headers)
    pid = create.json()["id"]
    resp = client.delete(f"/api/patients/{pid}", headers=second_doctor_headers)
    assert resp.status_code == 403


def test_admin_can_delete_any_patient(client, auth_headers, admin_headers):
    """管理员可以删除任意患者。"""
    create = client.post("/api/patients", json={"name": "Owner", "gender": "Male", "age": 12}, headers=auth_headers)
    pid = create.json()["id"]
    resp = client.delete(f"/api/patients/{pid}", headers=admin_headers)
    assert resp.status_code == 204
