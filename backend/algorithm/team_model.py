"""
算法对接模板：算法团队在此实现真实模型。

⚠️ 架构已更新（见 `algorithm/pipeline.py` 与 `contracts.py`）：
   真实实现请放在 **两个子模块** 里，不要再写在本文件：
       algorithm/detection/__init__.py       detect(image) -> ROI | None
       algorithm/classification/__init__.py  classify(roi)  -> ClassificationOutcome
   两个子模块的 `READY = True` 之后，`pipeline.py` 会自动切到真实流水线；
   本文件仅作为历史模板保留（平台 README 仍指向它）。

   本项目的实现位置：
       algorithm/model_core.py               共享模型核心（策略 / 阈值 / 安全网 / 权重加载）
       algorithm/detection/__init__.py       检测子模块（READY = True）
       algorithm/classification/__init__.py  分类子模块（READY = True）
       自检：`python -m algorithm.selftest <图片路径>`（平台自带，会打印走的是真实流水线还是 Mock）

参考写法（子模块契约）:
    # algorithm/detection/__init__.py
    from algorithm.contracts import ROI
    READY = True
    def detect(image):
        box, score = my_detector(image)
        return ROI(image=image, box=box, score=score)

    # algorithm/classification/__init__.py
    from algorithm.contracts import ClassificationOutcome
    READY = True
    def classify(roi):
        probs = my_classifier(roi.image)
        label = max(probs, key=probs.get)
        return ClassificationOutcome(classification=label, confidence=probs[label],
                                     class_probabilities=probs)

更多字段与校验规则，见 interface.py 顶部注释。
"""
