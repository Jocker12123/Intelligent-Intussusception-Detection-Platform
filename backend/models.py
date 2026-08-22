from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


def utcnow() -> datetime:
    """返回不带时区的 UTC 时间（避免 datetime.utcnow() 弃用警告，语义一致）。

    数据库统一存储 naive UTC，前端负责按本地时区换算显示。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="doctor")
    created_at = Column(DateTime, default=utcnow)

    patients = relationship("Patient", back_populates="creator")
    images = relationship("Image", back_populates="uploader")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=False)
    age = Column(Integer, nullable=False)
    medical_record_no = Column(String(50), nullable=True)
    clinical_symptoms = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    creator = relationship("User", back_populates="patients")
    images = relationship("Image", back_populates="patient", cascade="all, delete-orphan")


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=utcnow)

    patient = relationship("Patient", back_populates="images")
    uploader = relationship("User", back_populates="images")
    detection_result = relationship(
        "DetectionResult", back_populates="image",
        uselist=False, cascade="all, delete-orphan"
    )


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"), unique=True, nullable=False)
    classification = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    severity = Column(String(20), nullable=True)
    treatment_success_rate = Column(Float, nullable=True)
    treatment_advice = Column(Text, nullable=True)
    detected_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    model_name = Column(String(100), nullable=True)      # 产出结果的模型名
    model_version = Column(String(50), nullable=True)    # 模型版本
    inference_ms = Column(Float, nullable=True)          # 推理耗时(毫秒)
    class_probabilities = Column(Text, nullable=True)    # 各分类概率(JSON 文本)
    created_at = Column(DateTime, default=utcnow)

    image = relationship("Image", back_populates="detection_result")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False)          # create/update/delete/detect/login/logout/...
    resource = Column(String(50), nullable=False)        # patient/image/detection/settings/auth/...
    resource_id = Column(Integer, nullable=True)         # 关联记录的 ID（如有）
    detail = Column(Text, nullable=True)                 # 人类可读的描述
    ip_address = Column(String(64), nullable=True)       # 操作来源 IP
    created_at = Column(DateTime, default=utcnow, index=True)
