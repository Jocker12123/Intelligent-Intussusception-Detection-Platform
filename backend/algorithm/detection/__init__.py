"""检测模块（队友 A 负责）
=========================

职责：把输入图像 → 定位肠套叠病灶区域（ROI），交给分类模块。

对外契约（必须严格遵守）：
    def detect(image) -> ROI | None
        image : 已加载好的图像（numpy.ndarray，RGB 或灰度）
                —— 由适配层 pipeline.load_image() 统一读入（含 DICOM 解析）
        返回   : algorithm.contracts.ROI 对象
                 若模型未检出病灶，可以：
                   a) 返回 None                → 适配层会按"全图送分类"处理
                   b) 返回 ROI(image=原图)      → 明确表示全图送分类
                 两者都支持，按你的模型习惯来。

你可以在此目录下自由组织代码（model.py / weights/ 等），
只要求本包的 `detect` 函数签名不变。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
实现完成后：把下面的 READY 改成 True
适配层检测到两个模块都 READY，就会自动启用真实流水线。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

参考实现（把注释打开即可）:
    import numpy as np
    from algorithm.contracts import ROI

    def detect(image):
        # 1. 预处理
        x = preprocess(image)
        # 2. 你的检测模型推理
        box, score = my_model(x)          # 例如 (x1,y1,x2,y2), 0.93
        if box is None:
            return None
        # 3. 裁出 ROI（可选：也可不裁，直接回原图）
        x1, y1, x2, y2 = box
        roi_img = image[y1:y2, x1:x2]
        return ROI(image=roi_img, box=(x1, y1, x2, y2), score=score)
"""
from typing import Any, Optional

from algorithm.contracts import ROI

# ⚠️ 实现完成后改为 True，适配层才会启用你的检测模块
READY = False


def detect(image: Any) -> Optional[ROI]:
    """检测病灶区域。未实现前会抛错（适配层此时不会调用本函数）。"""
    raise NotImplementedError(
        "检测模块尚未实现：请在 backend/algorithm/detection/__init__.py 中"
        "实现 detect(image) -> ROI，并把 READY 改为 True"
    )
