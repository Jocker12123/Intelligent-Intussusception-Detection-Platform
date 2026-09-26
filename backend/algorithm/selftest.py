"""算法自测脚本（给算法队友用，也方便平台方排查）
=================================================

用法（在 backend 目录下执行）:
    .\\venv\\Scripts\\python.exe -m algorithm.selftest 路径\\到\\图片.jpg

它会：
  1. 显示两个子模块的 READY 状态（判断走的是真实流水线还是 Mock）
  2. 调用平台同一条入口 detect_intussusception()
  3. 打印返回结果，并校验是否合法（分类是否在三类内、置信度是否 0~1）

请在交给平台方之前，先用它把格式跑通。
"""
import sys
from pathlib import Path

VALID = {"肠套叠阳性", "肠套叠阴性", "图像质量不佳"}


def main() -> int:
    # 兼容 Windows 控制台编码：遇到打不出的字符时替换而不是崩溃
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("用法: python -m algorithm.selftest <图片路径>")
        return 2

    img_path = Path(sys.argv[1])
    if not img_path.exists():
        print(f"[错误] 文件不存在: {img_path}")
        return 2

    from algorithm import detection, classification
    from algorithm.pipeline import detect_intussusception, is_real_ready

    d_ready = bool(getattr(detection, "READY", False))
    c_ready = bool(getattr(classification, "READY", False))
    print("=" * 52)
    print(f"检测模块 READY = {d_ready}")
    print(f"分类模块 READY = {c_ready}")
    print(f"当前走的是: {'真实流水线' if is_real_ready() else 'Mock 占位(两模块需都 READY)'}")
    print("=" * 52)

    result = detect_intussusception(img_path)

    print(f"classification         : {result.classification}")
    print(f"confidence             : {result.confidence}")
    print(f"severity               : {result.severity}")
    print(f"treatment_success_rate : {result.treatment_success_rate}")
    print(f"treatment_advice       : {result.treatment_advice}")
    print(f"class_probabilities    : {result.class_probabilities}")
    print(f"model_name / version   : {result.model_name} / {result.model_version}")

    # ---- 合法性校验 ----
    ok = True
    if result.classification not in VALID:
        print(f"[FAIL] classification 非法: {result.classification} (必须是三类之一)")
        ok = False
    if result.confidence is None or not (0.0 <= float(result.confidence) <= 1.0):
        print(f"[FAIL] confidence 非法: {result.confidence} (必须在 0~1)")
        ok = False
    if result.class_probabilities and not isinstance(result.class_probabilities, dict):
        print("[FAIL] class_probabilities 必须是 dict")
        ok = False

    print("-" * 52)
    print("结果: " + ("[OK] 格式合法，可以交付" if ok else "[FAIL] 格式有问题，请修正"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
