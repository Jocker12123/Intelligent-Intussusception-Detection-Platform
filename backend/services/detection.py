from pathlib import Path
from time import perf_counter
import json

from sqlalchemy.orm import Session
from models import DetectionResult as DetectionResultModel, Image
from algorithm.interface import detect_intussusception, DetectionResult, validate_result


class DetectionService:

    @staticmethod
    def run_detection(image: Image, db: Session) -> DetectionResultModel:
        image_path = Path(image.filepath)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image.filepath}")
        t0 = perf_counter()
        raw = detect_intussusception(image_path)
        inference_ms = round((perf_counter() - t0) * 1000, 2)
        result: DetectionResult = validate_result(raw)
        # 幂等：若已存在该影像的结果，先删除再重建（保证一对一，支持重新检测）
        existing = db.query(DetectionResultModel).filter(DetectionResultModel.image_id == image.id).first()
        if existing:
            db.delete(existing)
            db.flush()
        detection = DetectionResultModel(
            image_id=image.id,
            classification=result.classification,
            confidence=result.confidence,
            severity=result.severity,
            treatment_success_rate=result.treatment_success_rate,
            treatment_advice=result.treatment_advice,
            detected_by=image.uploaded_by,
            model_name=result.model_name or None,
            model_version=result.model_version or None,
            inference_ms=inference_ms,
            class_probabilities=json.dumps(result.class_probabilities, ensure_ascii=False) if result.class_probabilities else None,
        )
        db.add(detection)
        db.commit()
        db.refresh(detection)
        return detection
