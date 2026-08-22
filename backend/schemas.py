from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, field_serializer, field_validator


def _as_utc(dt: datetime) -> str:
    """把 naive UTC 时间序列化为带 +00:00 后缀的 ISO 字符串。

    数据库统一存 naive UTC；这里显式标注 UTC，前端/算法方无需猜测，
    直接用 new Date(iso) 即可换算成本地时间，避免 8 小时时区偏移。
    """
    if dt is None:
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class PatientCreate(BaseModel):
    name: str
    gender: str
    age: int
    medical_record_no: Optional[str] = None
    clinical_symptoms: Optional[str] = None


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    medical_record_no: Optional[str] = None
    clinical_symptoms: Optional[str] = None


class PatientOut(BaseModel):
    id: int
    name: str
    gender: str
    age: int
    medical_record_no: Optional[str] = None
    clinical_symptoms: Optional[str] = None
    created_at: datetime

    @field_serializer("created_at")
    def _ser_created_at(self, v: datetime) -> str:
        return _as_utc(v)

    model_config = {"from_attributes": True}


class PatientListItem(PatientOut):
    status: str = ""
    last_detect: Optional[str] = None

    model_config = {"from_attributes": True}


class PatientStats(BaseModel):
    total_patients: int = 0
    today_new: int = 0
    pending: int = 0
    positive: int = 0


class ImageOut(BaseModel):
    id: int
    patient_id: int
    filename: str
    file_size: int
    uploaded_at: datetime

    @field_serializer("uploaded_at")
    def _ser_uploaded_at(self, v: datetime) -> str:
        return _as_utc(v)

    model_config = {"from_attributes": True}


class ImageInfo(ImageOut):
    has_result: bool = False
    result_id: Optional[int] = None
    media_type: Optional[str] = None


class PatientDetail(PatientOut):
    images: List[ImageOut] = []


class DetectionResultOut(BaseModel):
    id: int
    image_id: int
    classification: str
    confidence: float
    severity: Optional[str] = None
    treatment_success_rate: Optional[float] = None
    treatment_advice: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    inference_ms: Optional[float] = None
    class_probabilities: Optional[dict] = None
    created_at: datetime
    image: Optional[ImageInfo] = None

    @field_validator("class_probabilities", mode="before")
    @classmethod
    def _parse_class_probabilities(cls, v):
        # 数据库存的是 JSON 字符串，这里在类型校验前解析成 dict
        if v is None:
            return None
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return None
        return v

    @field_serializer("created_at")
    def _ser_created_at(self, v: datetime) -> str:
        return _as_utc(v)

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _ser_created_at(self, v: datetime) -> str:
        return _as_utc(v)

    model_config = {"from_attributes": True}


class SettingItem(BaseModel):
    key: str
    value: str

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    settings: List[SettingItem]


class DetectionTaskOut(BaseModel):
    task_id: str
    image_id: int
    status: str                       # pending | running | done | failed
    progress: int
    result_id: Optional[int] = None
    error: Optional[str] = None


class DetectionTaskResult(BaseModel):
    task: DetectionTaskOut
    result: Optional[DetectionResultOut] = None


class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    size: int
    pages: int


class ResultsStats(BaseModel):
    total: int = 0
    positive: int = 0
    negative: int = 0
    poor_quality: int = 0
    avg_confidence: float = 0.0


class AuditLogOut(BaseModel):
    id: int
    user_id: int
    username: str
    action: str
    resource: str
    resource_id: Optional[int] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    @field_serializer("created_at")
    def _ser_created_at(self, v: datetime) -> str:
        return _as_utc(v)

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    code: int
    message: str
    detail: Optional[str] = None
