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


def test_cannot_delete_patient_with_result(client, auth_headers):
    """患者已有检测结果时禁止删除（保护科研数据）。"""
    import io
    create = client.post("/api/patients", json={"name": "Prot", "gender": "Male", "age": 12}, headers=auth_headers)
    pid = create.json()["id"]
    f = io.BytesIO(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n"
        b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x22\x00\x02\x11\x01\x03"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf\x20\xff\xd9"
    )
    up = client.post("/api/images/upload", files={"file": ("p.jpg", f, "image/jpeg")}, data={"patient_id": str(pid)}, headers=auth_headers)
    img_id = up.json()["id"]
    client.post(f"/api/images/{img_id}/detect", headers=auth_headers)
    resp = client.delete(f"/api/patients/{pid}", headers=auth_headers)
    assert resp.status_code == 409


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


def test_age_birth_date_mismatch_rejected(client, auth_headers):
    """年龄与出生日期明显不一致时应返回 400。"""
    resp = client.post(
        "/api/patients",
        json={"name": "Bad", "gender": "Male", "age": 120, "birth_date": "2024-01-01"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_age_birth_date_consistent_ok(client, auth_headers):
    """年龄与出生日期一致时应创建成功。"""
    from datetime import date
    # 约 12 个月前出生 → 月龄约 12，允许 ±2 容差
    import datetime as dt
    birth = dt.date.today().replace(year=dt.date.today().year - 1).isoformat()
    resp = client.post(
        "/api/patients",
        json={"name": "Ok", "gender": "Male", "age": 12, "birth_date": birth},
        headers=auth_headers,
    )
    assert resp.status_code == 201
