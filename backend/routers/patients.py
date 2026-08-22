from math import ceil
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import LOCAL_TIMEZONE
from database import get_db
from models import Patient, User, Image, DetectionResult
from schemas import PatientCreate, PatientUpdate, PatientOut, PatientListItem, PatientStats, PatientDetail, PaginatedResponse
from auth import get_current_user, can_manage
from services.audit import record_audit

router = APIRouter(prefix="/api/patients", tags=["patients"])


def _validate_age_birth(age: int | None, birth_date: str | None):
    """校验年龄(月)与出生日期是否一致。若不一致抛 HTTPException(400)。

    仅当两者都提供时校验；允许 ±2 个月的容差（月龄计算取整会差 1 个月）。
    """
    if age is None or not birth_date:
        return
    try:
        bd = datetime.strptime(birth_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="出生日期格式不正确，应为 YYYY-MM-DD")
    today = datetime.now(ZoneInfo(LOCAL_TIMEZONE)).date()
    # 计算月龄（不足一个月按 0 计）
    months = (today.year - bd.year) * 12 + (today.month - bd.month)
    if today.day < bd.day:
        months -= 1
    if abs(months - age) > 2:
        raise HTTPException(
            status_code=400,
            detail=f"年龄({age}个月)与出生日期({birth_date})不一致，按出生日期推算约 {max(months,0)} 个月",
        )


def _status_from_classification(classification: str, severity: str | None) -> str:
    """由分类+严重度得到前端使用的状态码。"""
    if classification == "肠套叠阴性":
        return "negative"
    if classification == "肠套叠阳性":
        sev = severity or ""
        return f"positive:{sev}"
    if classification == "图像质量不佳":
        return "poor_quality"
    return "undetected"


def _latest_result_map(db: Session, patient_ids: list[int]) -> dict[int, tuple]:
    """一次查询得到这些患者各自的最近一次检测结果，消除 N+1 查询。

    返回 {patient_id: (classification, severity, created_at)}。
    """
    if not patient_ids:
        return {}
    rows = (
        db.query(
            Image.patient_id,
            DetectionResult.classification,
            DetectionResult.severity,
            DetectionResult.created_at,
        )
        .join(DetectionResult, DetectionResult.image_id == Image.id)
        .filter(Image.patient_id.in_(patient_ids))
        .order_by(DetectionResult.created_at.desc())
        .all()
    )
    latest = {}
    seen = set()
    for pid, classification, severity, created_at in rows:
        if pid in seen:
            continue
        seen.add(pid)
        latest[pid] = (classification, severity, created_at)
    return latest


def _detect_count_map(db: Session, patient_ids: list[int]) -> dict[int, int]:
    """一次查询得到每个患者的检测次数，消除 N+1。"""
    if not patient_ids:
        return {}
    rows = (
        db.query(Image.patient_id, func.count(DetectionResult.id))
        .join(DetectionResult, DetectionResult.image_id == Image.id)
        .filter(Image.patient_id.in_(patient_ids))
        .group_by(Image.patient_id)
        .all()
    )
    return {pid: int(cnt) for pid, cnt in rows}


@router.get("/stats", response_model=PatientStats)
def get_patient_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = db.query(Patient).count()
    # 计算"今天"的起点（按医院当地时区），并把 local 的当日起点换算成 UTC 后再比较。
    # 数据库里 created_at 是 naive UTC，所以这里也换算成 naive UTC 进行比较。
    tz = ZoneInfo(LOCAL_TIMEZONE)
    now_local = datetime.now(tz)
    today_local_midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_local_midnight.astimezone(timezone.utc).replace(tzinfo=None)
    today_new = db.query(Patient).filter(Patient.created_at >= today_start_utc).count()

    patient_ids = [pid for (pid,) in db.query(Patient.id).all()]
    latest = _latest_result_map(db, patient_ids)
    pending = sum(1 for pid in patient_ids if pid not in latest)
    positive = 0
    for pid, (classification, severity, _) in latest.items():
        if _status_from_classification(classification, severity).startswith("positive"):
            positive += 1

    return PatientStats(
        total_patients=total,
        today_new=today_new,
        pending=pending,
        positive=positive,
    )


@router.get("/export")
def export_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出患者列表为 CSV（含检测统计）。"""
    items = db.query(Patient).order_by(Patient.created_at.desc()).all()
    patient_ids = [p.id for p in items]
    latest = _latest_result_map(db, patient_ids)
    detect_counts = _detect_count_map(db, patient_ids)

    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM，防止 Excel 打开中文乱码
    writer = csv.writer(buf)
    writer.writerow(["ID", "姓名", "性别", "年龄(月)", "出生日期", "病历号", "住院号", "检查部位", "临床症状", "检测次数", "最近状态", "最近检测(UTC)", "录入时间(UTC)"])
    for p in items:
        status = "undetected"
        last_detect = ""
        info = latest.get(p.id)
        if info:
            classification, severity, created_at = info
            status = _status_from_classification(classification, severity)
            if created_at:
                last_detect = created_at.replace(tzinfo=timezone.utc).isoformat()
        created = p.created_at.replace(tzinfo=timezone.utc).isoformat() if p.created_at else ""
        writer.writerow([
            p.id, p.name, p.gender, p.age, p.birth_date or "", p.medical_record_no or "",
            p.hospital_no or "", p.exam_part or "", p.clinical_symptoms or "",
            detect_counts.get(p.id, 0), status, last_detect, created,
        ])
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="patients.csv"'},
    )


@router.get("", response_model=PaginatedResponse)
def list_patients(
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Patient)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Patient.name.like(pattern)) | (Patient.medical_record_no.like(pattern))
        )
    total = query.count()
    items = query.order_by(Patient.created_at.desc()).offset((page - 1) * size).limit(size).all()
    patient_ids = [p.id for p in items]
    latest = _latest_result_map(db, patient_ids)
    detect_counts = _detect_count_map(db, patient_ids)
    enriched = []
    for p in items:
        data = PatientListItem.model_validate(p)
        data.detect_count = detect_counts.get(p.id, 0)
        info = latest.get(p.id)
        if info:
            classification, severity, created_at = info
            data.status = _status_from_classification(classification, severity)
            if created_at:
                data.last_detect = created_at.replace(tzinfo=timezone.utc).isoformat()
        else:
            data.status = "undetected"
            data.last_detect = None
        enriched.append(data)
    return PaginatedResponse(
        items=enriched,
        total=total, page=page, size=size, pages=max(1, ceil(total / size)),
    )


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(body: PatientCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _validate_age_birth(body.age, body.birth_date)
    patient = Patient(**body.model_dump(), created_by=current_user.id)
    db.add(patient)
    db.flush()
    record_audit(db, current_user, action="create", resource="patient", resource_id=patient.id,
                 detail=f"新增患者：{patient.name}", request=request)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.put("/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: int, body: PatientUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not can_manage(patient.created_by, current_user):
        raise HTTPException(status_code=403, detail="仅该患者的录入医生或管理员可编辑")
    # 用更新后的值做年龄/出生日期一致性校验
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
    _validate_age_birth(patient.age, patient.birth_date)
    record_audit(db, current_user, action="update", resource="patient", resource_id=patient.id,
                 detail=f"编辑患者：{patient.name}", request=request)
    db.commit()
    db.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not can_manage(patient.created_by, current_user):
        raise HTTPException(status_code=403, detail="仅该患者的录入医生或管理员可删除")
    # 保护科研数据：患者已有检测结果时禁止直接删除，避免连带删光历史数据。
    has_result = (
        db.query(DetectionResult)
        .join(Image, Image.id == DetectionResult.image_id)
        .filter(Image.patient_id == patient_id)
        .first()
        is not None
    )
    if has_result:
        raise HTTPException(
            status_code=409,
            detail="该患者已有检测记录，为保护科研数据禁止删除。可改用「删除影像」后重试。",
        )
    name = patient.name
    record_audit(db, current_user, action="delete", resource="patient", resource_id=patient_id,
                 detail=f"删除患者：{name}", request=request)
    db.delete(patient)
    db.commit()
    return None
