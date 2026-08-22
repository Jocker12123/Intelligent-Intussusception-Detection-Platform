from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Image, User, DetectionResult as DetectionResultModel
from schemas import DetectionTaskOut, DetectionTaskResult
from auth import get_current_user
from services.detection_tasks import submit_detection_task, get_task

router = APIRouter(prefix="/api/detection", tags=["detection"])


@router.post("/tasks/{image_id}", response_model=DetectionTaskOut, status_code=202)
def create_detection_task(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交异步检测任务，立即返回任务 id；实际检测在后台线程执行。"""
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    # 已有结果则直接完成，无需重跑
    existing = db.query(DetectionResultModel).filter(DetectionResultModel.image_id == image_id).first()
    if existing:
        return _to_task_out(image_id=image_id, status="done", progress=100, result_id=existing.id)
    task = submit_detection_task(image_id)
    return _to_task_out(image_id=task.image_id, status=task.status, progress=task.progress, result_id=task.result_id, error=task.error, task_id=task.id)


@router.get("/tasks/{task_id}", response_model=DetectionTaskResult)
def get_detection_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询任务状态；若已完成，附带检测结果。"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    out = DetectionTaskOut(
        task_id=task.id,
        image_id=task.image_id,
        status=task.status,
        progress=task.progress,
        result_id=task.result_id,
        error=task.error,
    )
    result = None
    if task.status == "done" and task.result_id is not None:
        row = db.query(DetectionResultModel).filter(DetectionResultModel.id == task.result_id).first()
        if row:
            from .images import _media_type_from_path
            out_result = _result_out(row, _media_type_from_path(row.image.filepath) if row.image else None)
            result = out_result
    return DetectionTaskResult(task=out, result=result)


def _to_task_out(image_id, status, progress, result_id=None, error=None, task_id=None):
    return DetectionTaskOut(
        task_id=task_id or "",
        image_id=image_id,
        status=status,
        progress=progress,
        result_id=result_id,
        error=error,
    )


def _result_out(row, media_type):
    """复用 DetectionResultOut 并补全媒体类型。"""
    from schemas import DetectionResultOut
    out = DetectionResultOut.model_validate(row)
    if out.image:
        out.image.media_type = media_type
    return out
