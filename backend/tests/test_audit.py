import io


def test_create_patient_writes_audit(client, auth_headers, admin_headers):
    """新增患者后应产生一条审计记录（用管理员查询）。"""
    client.post("/api/patients", json={"name": "Audit P", "gender": "Male", "age": 12}, headers=auth_headers)
    resp = client.get("/api/audit", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(r["resource"] == "patient" and r["action"] == "create" for r in data["items"])


def test_login_writes_audit(client, test_user, admin_headers):
    """登录成功后应产生 audit='login' 的审计记录（用管理员查询）。"""
    client.post("/api/auth/login", json={"username": "doctor1", "password": "password123"})
    resp = client.get("/api/audit", headers=admin_headers)
    assert resp.status_code == 200
    assert any(r["action"] == "login" for r in resp.json()["items"])


def test_audit_requires_admin(client, auth_headers):
    """普通医生不能查看审计日志。"""
    resp = client.get("/api/audit", headers=auth_headers)
    assert resp.status_code == 403


def test_audit_admin_can_view(client, admin_headers):
    """管理员可以查看审计日志。"""
    resp = client.get("/api/audit", headers=admin_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_audit_export_csv(client, admin_headers):
    """导出审计日志应返回 CSV。"""
    resp = client.get("/api/audit/export", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "操作人" in resp.text


def test_audit_date_filter(client, auth_headers, admin_headers):
    """按日期范围过滤审计日志。"""
    # 用"未来"的起始时间，应过滤掉所有记录
    resp = client.get("/api/audit", headers=admin_headers, params={"start": "2099-01-01T00:00:00"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
