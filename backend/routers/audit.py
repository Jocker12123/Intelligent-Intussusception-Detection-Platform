import csv
import io
from datetime import datetime, timezone
from math import ceil
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config import LOCAL_TIMEZONE
from database import get_db
from models import AuditLog, User
from schemas import AuditLogOut, PaginatedResponse
from auth import get_current_admin

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _apply_filters(query, search: str, resource: str, start: str, end: str):
    """把搜索/资源/日期范围过滤应用到查询。

    数据库 created_at 为 naive UTC；日期范围按医院当地时区的自然日换算成 UTC 边界。
    """
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (AuditLog.username.like(pattern))
            | (AuditLog.detail.like(pattern))
            | (AuditLog.action.like(pattern))
        )
    if resource:
        query = query.filter(AuditLog.resource == resource)
    if start:
        # start 为本地当日 00:00，换算成 naive UTC
        try:
            start_local = datetime.fromisoformat(start)
            # 未带时区则按医院时区解释
            if start_local.tzinfo is None:
                start_local = start_local.replace(tzinfo=ZoneInfo(LOCAL_TIMEZONE))
            start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
            query = query.filter(AuditLog.created_at >= start_utc)
        except ValueError:
            pass
    if end:
        try:
            end_local = datetime.fromisoformat(end)
            if end_local.tzinfo is None:
                end_local = end_local.replace(tzinfo=ZoneInfo(LOCAL_TIMEZONE))
            end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
            query = query.filter(AuditLog.created_at <= end_utc)
        except ValueError:
            pass
    return query


def _filtered_query(db: Session, search: str, resource: str, start: str, end: str):
    return _apply_filters(db.query(AuditLog), search, resource, start, end)


@router.get("", response_model=PaginatedResponse)
def list_audit_logs(
    search: str = Query(default=""),
    resource: str = Query(default=""),
    start: str = Query(default=""),
    end: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """查看审计日志（仅管理员）。支持搜索、资源和日期范围过滤、分页。"""
    query = _filtered_query(db, search, resource, start, end)
    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return PaginatedResponse(
        items=[AuditLogOut.model_validate(r) for r in items],
        total=total, page=page, size=size, pages=max(1, ceil(total / size)),
    )


@router.get("/export")
def export_audit_logs(
    search: str = Query(default=""),
    resource: str = Query(default=""),
    start: str = Query(default=""),
    end: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """导出审计日志为 CSV（仅管理员）。"""
    query = _filtered_query(db, search, resource, start, end)
    items = query.order_by(AuditLog.created_at.desc()).all()

    buf = io.StringIO()
    # 写入 UTF-8 BOM，避免 Excel 打开时中文乱码
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(["ID", "时间(UTC)", "操作人", "操作", "对象", "对象ID", "详情", "来源IP"])
    for r in items:
        created = r.created_at.replace(tzinfo=timezone.utc).isoformat() if r.created_at else ""
        writer.writerow([r.id, created, r.username, r.action, r.resource, r.resource_id or "", r.detail or "", r.ip_address or ""])
    buf.seek(0)

    filename = "audit_logs.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
