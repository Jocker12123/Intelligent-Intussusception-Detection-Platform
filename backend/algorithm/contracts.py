"""算法内部数据契约（A 与 B 之间的接口）
==========================================

这是**检测模块**与**分类模块**之间约定的数据格式。
两人只需遵守这里的定义，各自内部实现随便改，互不影响。

约定：
    检测模块  detect(image)      -> ROI | None
    分类模块  classify(roi)      -> ClassificationOutcome

适配层（pipeline.py）负责把两者串起来，并转成平台契约 DetectionResult。
"""
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple


@dataclass
class ROI:
    """检测模块的输出，也是分类模块的输入。

    image: 交给分类模块的图像数据。
           - 通常是预处理后的图（numpy.ndarray）
           - 若检测模块不方便裁剪，也可直接放原图（约定"全图送分类"）
    box:   病灶在原图中的框 (x1, y1, x2, y2)，**可选**。
           目前平台暂不展示病灶框，先保留着，将来要展示时可直接用。
    score: 检测置信度（0~1），**可选**。
    """
    image: Any
    box: Optional[Tuple[int, int, int, int]] = None
    score: Optional[float] = None


@dataclass
class ClassificationOutcome:
    """分类模块的输出（由适配层转成平台契约）。

    classification / confidence 必填，其余可选。
    """
    classification: str                      # 必填: 肠套叠阳性 | 肠套叠阴性 | 图像质量不佳
    confidence: float                        # 必填: 0.0 ~ 1.0
    severity: Optional[str] = None           # 可选: 轻度 | 中度 | 重度（仅阳性）
    treatment_success_rate: Optional[float] = None  # 可选: 0.0 ~ 1.0（仅阳性）
    treatment_advice: str = ""               # 可选: 治疗建议文本
    class_probabilities: Optional[dict] = None      # 可选: 三类各自概率
