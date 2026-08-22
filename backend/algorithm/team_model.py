"""
算法对接模板：算法团队在此实现真实模型。

你只需要实现 `detect_intussusception` 函数，接口已定义在 interface.py。
平台侧（DetectionService）已把影像路径、存储和结果落库都处理好，你专注推理即可。

推荐写法（最小示例，仅写必填项即可跑通）:
    from pathlib import Path
    from algorithm.interface import DetectionResult

    def detect_intussusception(image_path: Path) -> DetectionResult:
        # 1. 加载你的模型
        # 2. 读取/预处理 image_path （支持 jpg/png/bmp/dicom）
        # 3. 推理
        # 4. 返回结果（可只填必填项）
        return DetectionResult(
            classification="肠套叠阳性",
            confidence=0.92,
        )

更多字段与校验规则，见 interface.py 顶部注释。
"""
