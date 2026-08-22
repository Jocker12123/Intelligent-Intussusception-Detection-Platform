from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from database import get_db
from models import SystemSetting, User
from schemas import SettingItem, SettingsUpdate
from auth import get_current_user, get_current_admin
from services.audit import record_audit

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=list[SettingItem])
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    settings = db.query(SystemSetting).all()
    return [SettingItem.model_validate(s) for s in settings]


@router.put("")
def update_settings(
    body: SettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    for item in body.settings:
        existing = db.query(SystemSetting).filter(SystemSetting.key == item.key).first()
        if existing:
            existing.value = item.value
        else:
            db.add(SystemSetting(key=item.key, value=item.value))
    changed = ", ".join(f"{s.key}='{s.value}'" for s in body.settings)
    record_audit(db, current_user, action="update", resource="settings",
                 detail=f"修改系统设置：{changed}", request=request)
    db.commit()
    return {"message": "设置已更新"}
