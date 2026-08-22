"""
算法接入接口协议
=================

算法团队只需要实现 `detect_intussusception`，即可把真实模型接入平台。
平台侧（DetectionService）已经帮你把路径、存储、落库都处理好了，你只需要返回结果。

接口定义:
    def detect_intussusception(image_path: Path) -> DetectionResult
        - image_path: 待检测的超声影像文件路径（平台已上传到 uploads/）
        - 返回: DetectionResult 对象

DetectionResult 字段:
    classification          str     必填. "肠套叠阳性" | "肠套叠阴性" | "图像质量不佳"
    confidence              float   必填. 0.0 ~ 1.0
    severity                str|None 可选. 仅阳性时有意义: "轻度" | "中度" | "重度"
    treatment_success_rate  float|None 可选. 仅阳性时有意义: 0.0 ~ 1.0（灌肠复位成功率）
    treatment_advice        str     可选. 治疗建议文本

注意: severity / treatment_success_rate / treatment_advice 都可以忽略不填，
平台会按分类给出默认值，不会让你的代码因为缺字段报错。

推荐写法（最小示例，仅写必填项也能跑通）:
    from pathlib import Path
    from algorithm.interface import DetectionResult

    def detect_intussusception(image_path: Path) -> DetectionResult:
        # 1. 加载你的模型
        # 2. 读取/预处理 image_path
        # 3. 推理
        # 4. 返回结果（可只填必填项）
        return DetectionResult(
            classification="肠套叠阳性",
            confidence=0.95,
        )
"""
import hashlib
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DetectionResult:
    """算法团队返回的检测结果。必填项之外的字段都有默认值，可省略。"""

    classification: str
    confidence: float
    severity: Optional[str] = None
    treatment_success_rate: Optional[float] = None
    treatment_advice: str = ""
    # 模型元数据（可选）：用于平台记录/追溯是哪个模型产出的结果
    model_name: str = ""
    model_version: str = ""
    # 各分类概率（可选）：{"肠套叠阳性":0.8,"肠套叠阴性":0.1,"图像质量不佳":0.1}
    # 平台会校验并归一化；若未提供，则前端用 confidence 兜底展示。
    class_probabilities: Optional[dict] = None


# 平台认可的分类集合（用于校验算法返回是否合法）
VALID_CLASSIFICATIONS = {"肠套叠阳性", "肠套叠阴性", "图像质量不佳"}
VALID_SEVERITIES = {"轻度", "中度", "重度"}


def _default_advice(classification: str, severity: Optional[str] = None,
                    treatment_success_rate: Optional[float] = None) -> str:
    """为缺省字段给出默认建议，保证前端/报告永远有内容可显示。"""
    if classification == "肠套叠阳性":
        rate = int((treatment_success_rate or 0.85) * 100)
        return f"建议立即行空气灌肠复位术（预估成功率{rate}%）。复位失败需急诊手术。"
    if classification == "肠套叠阴性":
        return "超声未见肠套叠征象。建议结合临床观察，无需特殊治疗。"
    if classification == "图像质量不佳":
        return "图像质量不满足诊断要求，请重新拍摄。"
    return ""


def validate_result(result: DetectionResult) -> DetectionResult:
    """校验并规范化算法返回，避免脏数据进入数据库/前端。

    - 分类不在合法集合内时，按"图像质量不佳"兜底
    - 置信度收敛到 [0, 1]
    - 必填缺省项自动补齐
    """
    classification = result.classification if result.classification in VALID_CLASSIFICATIONS else "图像质量不佳"
    confidence = max(0.0, min(1.0, float(result.confidence or 0.0)))
    severity = result.severity if result.severity in VALID_SEVERITIES else None
    rate = result.treatment_success_rate
    if rate is not None:
        rate = max(0.0, min(1.0, float(rate)))
    if classification == "肠套叠阴性" or classification == "图像质量不佳":
        severity = None
        rate = None
    advice = result.treatment_advice or _default_advice(classification, severity, rate)
    probs = _normalize_probabilities(result.class_probabilities, classification, confidence)
    return DetectionResult(
        classification=classification,
        confidence=confidence,
        severity=severity,
        treatment_success_rate=rate,
        treatment_advice=advice,
        model_name=result.model_name or "",
        model_version=result.model_version or "",
        class_probabilities=probs,
    )


def _normalize_probabilities(probs, classification: str, confidence: float) -> dict | None:
    """校验并归一化各分类概率。

    - 仅保留合法分类
    - 每个值收敛到 [0,1]
    - 若总和无意义（缺失/全 0），则用 `{classification: confidence}` 兜底
    """
    if not isinstance(probs, dict):
        return None
    cleaned = {}
    for key, val in probs.items():
        if key not in VALID_CLASSIFICATIONS:
            continue
        try:
            cleaned[key] = max(0.0, min(1.0, float(val)))
        except (TypeError, ValueError):
            continue
    total = sum(cleaned.values())
    if total <= 0:
        return {classification: round(confidence, 4)}
    return {k: round(v / total, 4) for k, v in cleaned.items()}


def detect_intussusception(image_path: Path) -> DetectionResult:
    """Mock 实现（演示用）。

    提示: 这是平台内置的占位实现，用于在没有真实模型时跑通前后端流程。
    算法团队实现真实模型时，替换本函数即可（保持函数名和签名不变）。

    为保证可复现（同一张图多次检测结果一致），用文件内容哈希作随机种子，
    而不是每次随机——这样演示数据更稳定、便于测试。
    """
    seed = 0
    try:
        with open(image_path, "rb") as f:
            seed = int(hashlib.md5(f.read(4096)).hexdigest(), 16)
    except Exception:
        pass
    rng = random.Random(seed)

    classifications = ["肠套叠阴性", "肠套叠阳性", "图像质量不佳"]
    # 演示用：阴性权重略高，让结果更接近真实分布
    classification = rng.choices(classifications, weights=[5, 3, 2])[0]
    confidence = round(rng.uniform(0.75, 0.99), 4)

    # 构造一个围绕命中类别的概率分布（其余类别分走剩余概率）
    remaining = round(max(0.0, 1.0 - confidence) * rng.uniform(0.3, 1.0), 4)
    probs = {c: 0.0 for c in classifications}
    for c in classifications:
        if c == classification:
            probs[c] = confidence
        else:
            probs[c] = round(remaining / 2, 4)
    probs = {k: round(v / sum(probs.values()), 4) for k, v in probs.items()}

    if classification == "肠套叠阳性":
        severity = rng.choice(["轻度", "中度", "重度"])
        treatment_success_rate = round(rng.uniform(0.80, 0.98), 2)
        advice = f"建议立即行空气灌肠复位术（预估成功率{int(treatment_success_rate * 100)}%）。复位失败需急诊手术。"
    else:
        severity = None
        treatment_success_rate = None
        advice = _default_advice(classification)

    return DetectionResult(
        classification=classification,
        confidence=confidence,
        severity=severity,
        treatment_success_rate=treatment_success_rate,
        treatment_advice=advice,
        model_name="Mock",
        model_version="1.0.0",
        class_probabilities=probs,
    )
