from math import ceil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models import DetectionResult as DetectionResultModel, User
from schemas import DetectionResultOut, PaginatedResponse, ResultsStats
from auth import get_current_user
from .images import _media_type_from_path

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/stats", response_model=ResultsStats)
def get_results_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """全量检测统计（用于检测记录页概览）。"""
    rows = db.query(
        DetectionResultModel.classification,
        DetectionResultModel.confidence,
    ).all()
    total = len(rows)
    positive = sum(1 for c, _ in rows if c == "肠套叠阳性")
    negative = sum(1 for c, _ in rows if c == "肠套叠阴性")
    poor_quality = sum(1 for c, _ in rows if c == "图像质量不佳")
    confs = [conf for _, conf in rows if conf is not None]
    avg_confidence = round(sum(confs) / len(confs), 4) if confs else 0.0
    return ResultsStats(
        total=total,
        positive=positive,
        negative=negative,
        poor_quality=poor_quality,
        avg_confidence=avg_confidence,
    )


@router.get("", response_model=PaginatedResponse)
def list_results(
    patient_id: int = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(DetectionResultModel)
    if patient_id is not None:
        query = query.filter(DetectionResultModel.image.has(patient_id=patient_id))
    total = query.count()
    items = query.order_by(DetectionResultModel.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return PaginatedResponse(
        items=[DetectionResultOut.model_validate(r) for r in items],
        total=total, page=page, size=size, pages=max(1, ceil(total / size)),
    )


@router.get("/{result_id}", response_model=DetectionResultOut)
def get_result(result_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = db.query(DetectionResultModel).filter(DetectionResultModel.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    out = DetectionResultOut.model_validate(result)
    # 补全嵌套影像的媒体类型，前端据此判断 DICOM 是否可在线预览
    if out.image:
        out.image.media_type = _media_type_from_path(result.image.filepath)
    return out
