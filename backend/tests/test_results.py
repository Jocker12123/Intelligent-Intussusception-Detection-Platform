import io

def _setup(client, auth_headers):
    pid = client.post("/api/patients", json={"name": "R", "gender": "Male", "age": 12}, headers=auth_headers).json()["id"]
    f = io.BytesIO(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n"
        b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x22\x00\x02\x11\x01\x03"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf\x20\xff\xd9"
    )
    up = client.post("/api/images/upload", files={"file": ("r.jpg", f, "image/jpeg")}, data={"patient_id": str(pid)}, headers=auth_headers)
    img_id = up.json()["id"]
    det = client.post(f"/api/images/{img_id}/detect", headers=auth_headers)
    return pid, det.json()["id"]


def test_get_result(client, auth_headers):
    _, rid = _setup(client, auth_headers)
    resp = client.get(f"/api/results/{rid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["classification"] is not None


def test_list_results(client, auth_headers):
    _setup(client, auth_headers)
    resp = client.get("/api/results", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_get_result_not_found(client, auth_headers):
    resp = client.get("/api/results/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_get_results_stats(client, auth_headers):
    _setup(client, auth_headers)
    resp = client.get("/api/results/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert "positive" in data
    assert "negative" in data
    assert "avg_confidence" in data
    assert 0.0 <= data["avg_confidence"] <= 1.0
    assert 0.0 <= data["positive_rate"] <= 1.0
    assert 0.0 <= data["negative_rate"] <= 1.0


def test_export_results_csv(client, auth_headers):
    _setup(client, auth_headers)
    resp = client.get("/api/results/export", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "患者" in resp.text and "分类" in resp.text


def test_async_detection_task_with_existing_result(client, auth_headers):
    """已有检测结果时，提交异步任务应直接返回 done。"""
    pid = client.post("/api/patients", json={"name": "A", "gender": "Male", "age": 12}, headers=auth_headers).json()["id"]
    f = io.BytesIO(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n"
        b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x22\x00\x02\x11\x01\x03"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf\x20\xff\xd9"
    )
    up = client.post("/api/images/upload", files={"file": ("a.jpg", f, "image/jpeg")}, data={"patient_id": str(pid)}, headers=auth_headers)
    img_id = up.json()["id"]
    # 先跑一次同步检测，产生结果
    det = client.post(f"/api/images/{img_id}/detect", headers=auth_headers)
    rid = det.json()["id"]
    # 再提交异步任务，应直接 done
    task_res = client.post(f"/api/detection/tasks/{img_id}", headers=auth_headers)
    assert task_res.status_code == 202
    assert task_res.json()["status"] == "done"
    assert task_res.json()["result_id"] == rid
