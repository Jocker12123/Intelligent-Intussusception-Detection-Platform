from math import ceil
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from config import LOCAL_TIMEZONE
from database import get_db
from models import Patient, User, Image, DetectionResult
from schemas import PatientCreate, PatientUpdate, PatientOut, PatientListItem, PatientStats, PatientDetail, PaginatedResponse
from auth import get_current_user, can_manage
from services.audit import record_audit

router = APIRouter(prefix="/api/patients", tags=["patients"])


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
    latest = _latest_result_map(db, [p.id for p in items])
    enriched = []
    for p in items:
        data = PatientListItem.model_validate(p)
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
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
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
    name = patient.name
    record_audit(db, current_user, action="delete", resource="patient", resource_id=patient_id,
                 detail=f"删除患者：{name}", request=request)
    db.delete(patient)
    db.commit()
    return None
