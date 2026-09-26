"""分类模块（队友 B 负责）
=========================

职责：接收检测模块给出的 ROI → 输出三分类结果（阳性 / 阴性 / 图像质量不佳）。

对外契约（必须严格遵守）：
    def classify(roi) -> ClassificationOutcome
        roi   : algorithm.contracts.ROI（含 image 字段，以及可选的 box/score）
                注意：roi.image 可能已经是裁剪好的病灶图；
                      若检测模块没有裁剪，则是整张原图 —— 请自行兼容。
        返回   : algorithm.contracts.ClassificationOutcome 对象
                至少填 classification + confidence

你可以在此目录下自由组织代码，只要求本包的 `classify` 函数签名不变。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
实现完成后：把下面的 READY 改成 True
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

参考实现（把注释打开即可）:
    from algorithm.contracts import ClassificationOutcome

    def classify(roi):
        x = preprocess(roi.image)
        probs = my_model(x)      # {"肠套叠阳性":0.9, ...}
        label = max(probs, key=probs.get)
        return ClassificationOutcome(
            classification=label,
            confidence=probs[label],
            class_probabilities=probs,
        )
"""
from typing import Any

from algorithm.contracts import ClassificationOutcome, ROI

# ⚠️ 实现完成后改为 True，适配层才会启用你的分类模块
READY = False


def classify(roi: ROI) -> ClassificationOutcome:
    """分类。未实现前会抛错（适配层此时不会调用本函数）。"""
    raise NotImplementedError(
        "分类模块尚未实现：请在 backend/algorithm/classification/__init__.py 中"
        "实现 classify(roi) -> ClassificationOutcome，并把 READY 改为 True"
    )
