"""审计日志服务：记录"谁、在何时、做了什么"。

医疗系统需要可追溯的操作记录。平台各路由在关键操作后调用 `record_audit`，
把操作写入 audit_logs 表。查询接口见 routers/audit.py（仅管理员可见）。
"""
from sqlalchemy.orm import Session
from fastapi import Request
from models import AuditLog, User


def get_client_ip(request: Request | None) -> str:
    """取客户端来源 IP。优先取反向代理头，其次用直连地址。"""
    if request is None:
        return ""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def record_audit(
    db: Session,
    user: User,
    action: str,
    resource: str,
    resource_id: int | None = None,
    detail: str = "",
    request: Request | None = None,
) -> None:
    """写入一条审计记录。通常在业务操作成功后调用（与业务同一次 db.commit）。"""
    log = AuditLog(
        user_id=user.id,
        username=user.username,
        action=action,
        resource=resource,
        resource_id=resource_id,
        detail=detail,
        ip_address=get_client_ip(request),
    )
    db.add(log)
