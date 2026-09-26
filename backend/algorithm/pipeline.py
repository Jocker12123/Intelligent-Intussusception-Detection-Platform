"""薄适配层：把「检测(A) + 分类(B)」串成平台唯一入口
=====================================================

平台只依赖这一个函数：
    detect_intussusception(image_path: Path) -> DetectionResult

工作方式（**自动切换，不需要改平台代码**）：
    ┌─ detection.READY 且 classification.READY 都为 True
    │     → 走真实流水线：读图 → 检测(A) → 分类(B) → 组装结果
    └─ 否则
          → 自动回退到 interface.py 里的 Mock（保证平台随时能跑通）

所以现在的状态：两人模块都是 READY=False，平台照常跑 Mock。
等他们把各自模块实现好、把 READY 改成 True，真实模型就自动生效。

本文件是两人代码的**唯一交汇点**，保持轻薄、写完基本不动。
"""
import logging
from pathlib import Path

from algorithm.interface import (
    DetectionResult,
    detect_intussusception as _mock_detect,
    validate_result,
)
from algorithm.contracts import ROI
from algorithm import detection
from algorithm import classification

logger = logging.getLogger("uvicorn.error")

# 只提示一次，避免刷屏
_warned_mock = False


def is_real_ready() -> bool:
    """两个子模块是否都已就绪。"""
    return bool(getattr(detection, "READY", False)) and bool(getattr(classification, "READY", False))


def load_image(image_path: Path):
    """把影像文件读成图像数组。

    - 普通图片(jpg/png/bmp)：用 Pillow 读取并转 RGB
    - DICOM(.dcm)：用 pydicom 读取像素

    注意：Pillow / numpy / pydicom 属于算法侧依赖，
    如果用到请把它们加入 backend/requirements.txt。
    """
    suffix = Path(image_path).suffix.lower()

    if suffix == ".dcm":
        try:
            import pydicom  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("读取 DICOM 需要安装 pydicom：pip install pydicom") from exc
        ds = pydicom.dcmread(str(image_path))
        return ds.pixel_array

    try:
        import numpy as np  # noqa: WPS433
        from PIL import Image  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("读取图片需要安装 Pillow 与 numpy：pip install pillow numpy") from exc
    return np.array(Image.open(image_path).convert("RGB"))


def detect_intussusception(image_path: Path) -> DetectionResult:
    """平台调用的唯一入口。"""
    global _warned_mock

    if not is_real_ready():
        if not _warned_mock:
            logger.warning(
                "算法模块尚未就绪（detection.READY / classification.READY 为 False），"
                "本次使用 Mock 结果。实现完成后把对应 READY 改为 True 即可自动启用。"
            )
            _warned_mock = True
        return _mock_detect(image_path)

    # ---- 真实流水线 ----
    img = load_image(image_path)          # 1) 读图（含 DICOM）
    roi = detection.detect(img)           # 2) 队友A：检测
    if roi is None:                       #    未检出病灶 → 按"全图送分类"处理
        roi = ROI(image=img)
    outcome = classification.classify(roi)  # 3) 队友B：分类

    # 4) 组装成平台契约（validate_result 会做合法性校验与兜底）
    return validate_result(DetectionResult(
        classification=outcome.classification,
        confidence=outcome.confidence,
        severity=outcome.severity,
        treatment_success_rate=outcome.treatment_success_rate,
        treatment_advice=outcome.treatment_advice,
        class_probabilities=outcome.class_probabilities,
        model_name="team-pipeline",
        model_version="1.0",
    ))
