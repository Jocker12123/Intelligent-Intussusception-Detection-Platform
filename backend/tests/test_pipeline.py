"""适配层（pipeline）测试：锁住 A/B 与平台的集成契约。

覆盖：
  1. 两个模块未就绪 → 自动回退 Mock（平台随时可用）
  2. 两个模块就绪 → 走真实流水线并正确组装 DetectionResult
  3. detect 返回 None → 按"全图送分类"处理
  4. 队友返回非法分类 → validate_result 兜底纠正
  5. 双模型溯源：A/B 的模型名、版本、分段耗时、检测置信度、病灶框
"""
from pathlib import Path

from algorithm import pipeline, detection, classification
from algorithm.contracts import ROI, ClassificationOutcome


def test_fallback_to_mock_when_not_ready(monkeypatch):
    """模块未就绪时，应回退到 Mock 且结果合法。"""
    monkeypatch.setattr(detection, "READY", False)
    monkeypatch.setattr(classification, "READY", False)
    assert pipeline.is_real_ready() is False

    result = pipeline.detect_intussusception(Path("not-used.jpg"))
    assert result.classification in {"肠套叠阳性", "肠套叠阴性", "图像质量不佳"}
    assert 0.0 <= float(result.confidence) <= 1.0


def test_real_pipeline_when_ready(monkeypatch):
    """两模块就绪时走真实流水线，并正确组装结果。"""
    monkeypatch.setattr(pipeline, "load_image", lambda p: "IMG")
    monkeypatch.setattr(detection, "READY", True)
    monkeypatch.setattr(classification, "READY", True)
    monkeypatch.setattr(detection, "detect", lambda img: ROI(image="ROI", box=(1, 2, 3, 4), score=0.9))
    monkeypatch.setattr(
        classification, "classify",
        lambda roi: ClassificationOutcome(
            classification="肠套叠阳性",
            confidence=0.88,
            severity="中度",
            treatment_success_rate=0.9,
            class_probabilities={"肠套叠阳性": 0.88, "肠套叠阴性": 0.07, "图像质量不佳": 0.05},
        ),
    )
    assert pipeline.is_real_ready() is True

    result = pipeline.detect_intussusception(Path("x.jpg"))
    assert result.classification == "肠套叠阳性"
    assert result.confidence == 0.88
    assert result.severity == "中度"
    assert result.treatment_success_rate == 0.9
    assert result.model_name == "team-pipeline"


def test_detect_none_means_full_image(monkeypatch):
    """detect 返回 None 时，适配层应把整张原图交给分类。"""
    monkeypatch.setattr(pipeline, "load_image", lambda p: "FULL_IMG")
    monkeypatch.setattr(detection, "READY", True)
    monkeypatch.setattr(classification, "READY", True)
    monkeypatch.setattr(detection, "detect", lambda img: None)

    captured = {}

    def fake_classify(roi):
        captured["roi"] = roi
        return ClassificationOutcome(classification="肠套叠阴性", confidence=0.7)

    monkeypatch.setattr(classification, "classify", fake_classify)

    result = pipeline.detect_intussusception(Path("x.jpg"))
    assert captured["roi"].image == "FULL_IMG"     # 收到的是全图
    assert captured["roi"].box is None
    assert result.classification == "肠套叠阴性"


def test_invalid_classification_is_corrected(monkeypatch):
    """队友返回非法分类时，validate_result 应兜底为「图像质量不佳」。"""
    monkeypatch.setattr(pipeline, "load_image", lambda p: "IMG")
    monkeypatch.setattr(detection, "READY", True)
    monkeypatch.setattr(classification, "READY", True)
    monkeypatch.setattr(detection, "detect", lambda img: ROI(image="ROI"))
    monkeypatch.setattr(
        classification, "classify",
        lambda roi: ClassificationOutcome(classification="随便写的分类", confidence=1.5),
    )

    result = pipeline.detect_intussusception(Path("x.jpg"))
    assert result.classification == "图像质量不佳"   # 非法分类被纠正
    assert result.confidence == 1.0                 # 越界置信度被收敛


def test_mock_leaves_model_slots_empty(monkeypatch):
    """Mock 是整条流水线的占位实现，不应伪造检测/分类模型名。"""
    monkeypatch.setattr(detection, "READY", False)
    monkeypatch.setattr(classification, "READY", False)

    result = pipeline.detect_intussusception(Path("not-used.jpg"))
    assert result.model_name == "Mock"
    assert result.detection_model_name == ""
    assert result.classification_model_name == ""
    assert result.detection_ms is None
    assert result.classification_ms is None


def test_real_pipeline_records_both_models(monkeypatch):
    """就绪时应分别记录 A/B 的模型名、版本、耗时，以及检测原始输出。"""
    monkeypatch.setattr(pipeline, "load_image", lambda p: "IMG")
    monkeypatch.setattr(detection, "READY", True)
    monkeypatch.setattr(classification, "READY", True)
    monkeypatch.setattr(detection, "NAME", "DetA")
    monkeypatch.setattr(detection, "VERSION", "1.2.3")
    monkeypatch.setattr(classification, "NAME", "ClsB")
    monkeypatch.setattr(classification, "VERSION", "2.0")
    monkeypatch.setattr(detection, "detect", lambda img: ROI(image="ROI", box=(10, 20, 30, 40), score=0.93))
    monkeypatch.setattr(
        classification, "classify",
        lambda roi: ClassificationOutcome(classification="肠套叠阳性", confidence=0.88),
    )

    result = pipeline.detect_intussusception(Path("x.jpg"))
    assert result.detection_model_name == "DetA"
    assert result.detection_model_version == "1.2.3"
    assert result.classification_model_name == "ClsB"
    assert result.classification_model_version == "2.0"
    assert result.detection_score == 0.93
    assert result.roi_box == (10, 20, 30, 40)
    assert result.detection_ms is not None and result.detection_ms >= 0
    assert result.classification_ms is not None and result.classification_ms >= 0
    assert result.model_name == "team-pipeline"      # 整体标签保留


def test_detection_model_recorded_even_when_no_roi(monkeypatch):
    """detect 返回 None（未检出病灶）时，仍要记下是哪个检测模型跑过。"""
    monkeypatch.setattr(pipeline, "load_image", lambda p: "FULL_IMG")
    monkeypatch.setattr(detection, "READY", True)
    monkeypatch.setattr(classification, "READY", True)
    monkeypatch.setattr(detection, "NAME", "DetA")
    monkeypatch.setattr(detection, "detect", lambda img: None)
    monkeypatch.setattr(
        classification, "classify",
        lambda roi: ClassificationOutcome(classification="肠套叠阴性", confidence=0.7),
    )

    result = pipeline.detect_intussusception(Path("x.jpg"))
    assert result.detection_model_name == "DetA"
    assert result.detection_score is None
    assert result.roi_box is None


def test_validate_result_sanitizes_model_metadata():
    """脏的模型元数据不应进入数据库：超长截断、非法耗时/框丢弃、置信度收敛。"""
    from algorithm.interface import DetectionResult, validate_result

    dirty = DetectionResult(
        classification="肠套叠阳性",
        confidence=0.9,
        detection_model_name="  " + "X" * 200 + "  ",
        detection_model_version="V" * 80,
        detection_ms=-5,
        classification_ms="abc",
        detection_score=1.7,
        roi_box=(1, 2, 3),
    )
    clean = validate_result(dirty)
    assert clean.detection_model_name == "X" * 100          # 限长到列宽
    assert clean.detection_model_version == "V" * 50
    assert clean.detection_ms is None                       # 负数耗时丢弃
    assert clean.classification_ms is None                  # 非数字耗时丢弃
    assert clean.detection_score == 1.0                     # 越界收敛
    assert clean.roi_box is None                            # 长度不对的框丢弃

    normalized = validate_result(DetectionResult(
        classification="肠套叠阳性", confidence=0.9,
        detection_ms=12.3456, roi_box=[1.9, 2.1, 3, 4],
    ))
    assert normalized.detection_ms == 12.35                 # 保留 2 位小数
    assert normalized.roi_box == (1, 2, 3, 4)

    negative_box = validate_result(DetectionResult(
        classification="肠套叠阳性", confidence=0.9, roi_box="not-a-box",
    ))
    assert negative_box.roi_box is None
