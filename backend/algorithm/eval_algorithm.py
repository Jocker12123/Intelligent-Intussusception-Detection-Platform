"""端到端验证脚本（算法侧自用）
================================

用途：按平台同一条入口验证真实实现是否正确、以及报的是真实模型还是 Mock。

用法（在 backend 目录下）:
    <python> -m algorithm.eval_algorithm 图片路径                    # 单张，打印完整结果
    <python> -m algorithm.eval_algorithm --pos 目录A 目录B ... --neg 目录C ...
                                                                     # 批量，打印混淆矩阵与指标

它会先打印：
    · 检测/分类子模块的 READY 状态、当前走的是「真实流水线」还是 Mock 兜底
    · 当前策略摘要（policy / version / 阈值 / 模型数 / 安全网 / 权重目录）
再跑推理，并校验返回值合法（三类之一、置信度 0~1）。

批量模式下额外给出两套指标：
    · 按当前配置（安全网开/关以 model_core.SAFETY_NET 为准）
    · 把安全网关掉后的等价指标（由同一次推理的分数复原，不重复推理）
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# 允许 `python algorithm/eval_algorithm.py` 直接跑（把 backend 加进 sys.path）
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

VALID = {"肠套叠阳性", "肠套叠阴性", "图像质量不佳"}
IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".dcm")


def _print_env():
    from algorithm import classification, detection, model_core
    from algorithm.pipeline import is_real_ready

    print("=" * 74)
    print(f"检测子模块 READY = {bool(getattr(detection, 'READY', False))}")
    print(f"分类子模块 READY = {bool(getattr(classification, 'READY', False))}")
    real = is_real_ready()
    print(f"当前走的是      = {'★ 真实流水线' if real else '⚠ Mock 占位（两模块需都 READY）'}")
    print("-" * 74)
    if real:
        d = model_core.describe()
        for k in ("policy", "version", "threshold", "fusion", "n_models", "n_inference_passes",
                  "weights_present", "safety_net", "safety_rule", "v2_threshold_calibrated", "weight_dir"):
            print(f"  {k:<22}= {d[k]}")
    else:
        from algorithm.interface import detect_intussusception as _mock
        print("  ⚠ 真实模型未启用，返回的 model_name 会是 'Mock（占位实现·非真实模型）'，")
        print("     treatment_advice 会以 '【演示用 Mock 结果...】' 开头。")
    print("=" * 74)


def _one(path: Path, verbose: bool = True):
    from algorithm.pipeline import detect_intussusception

    t0 = time.perf_counter()
    r = detect_intussusception(path)
    ms = (time.perf_counter() - t0) * 1000

    ok = True
    if r.classification not in VALID:
        print(f"[FAIL] classification 非法: {r.classification}")
        ok = False
    if r.confidence is None or not (0.0 <= float(r.confidence) <= 1.0):
        print(f"[FAIL] confidence 非法: {r.confidence}")
        ok = False
    if verbose:
        print(f"  文件                   : {path.name}")
        print(f"  classification         : {r.classification}")
        print(f"  confidence             : {r.confidence}")
        print(f"  model_name / version   : {r.model_name} / {r.model_version}")
        print(f"  class_probabilities    : {r.class_probabilities}")
        print(f"  treatment_advice       : {r.treatment_advice}")
        print(f"  耗时                   : {ms:.0f} ms")
    return r, ok, ms


def _pred_positive(r) -> bool:
    """仅按模型证据分是否判阳（即把安全网关掉后的判定）。

    ※ confidence 现在是**标定后的置信度**，不再等于原始证据分；
      但标定单调，故 `证据分 >= 阈值  <=>  置信度 >= 标定(阈值)`，可直接比较。
      「图像质量不佳」由安全网（证据分 == 0）触发，一律不算阳性。
    """
    from algorithm import model_core as mc
    if r.classification != "肠套叠阳性":
        return False
    thr = float(mc.POLICIES[mc.POLICY]["threshold"])
    return float(r.confidence) >= mc.calibrate_positive(thr)


def _score_from_result(r) -> float:
    """从标定后的置信度反查原始证据分（单调表反查；饱和区间无法精确还原，仅供展示）。"""
    from algorithm import model_core as mc
    if r.classification != "肠套叠阳性":
        return 0.0
    conf = float(r.confidence)
    xs = [t[0] for t in mc.CALIB_POS]
    ys = [t[1] for t in mc.CALIB_POS]
    for i in range(1, len(ys)):
        if conf <= ys[i]:
            if ys[i] == ys[i - 1]:
                return float(xs[i - 1])
            k = (conf - ys[i - 1]) / (ys[i] - ys[i - 1])
            return float(xs[i - 1] + k * (xs[i] - xs[i - 1]))
    return 1.0


def batch(pos_dirs, neg_dirs, limit=None):
    from algorithm import model_core

    pos = [f for d in pos_dirs for f in sorted(Path(d).iterdir()) if f.suffix.lower() in IMG_EXTS]
    neg = [f for d in neg_dirs for f in sorted(Path(d).iterdir()) if f.suffix.lower() in IMG_EXTS]
    if limit:
        pos, neg = pos[:limit], neg[:limit]
    print(f"正样本 {len(pos)} 张 / 负样本 {len(neg)} 张   （安全网 SAFETY_NET={model_core.SAFETY_NET}）")
    thr = float(model_core.POLICIES[model_core.POLICY]["threshold"])

    rows = []; results_raw = []
    t0 = time.perf_counter()
    for i, (p, y) in enumerate([(f, 1) for f in pos] + [(f, 0) for f in neg], 1):
        r, ok, ms = _one(p, verbose=False)
        if not ok:
            print(f"  [FAIL] {p.name}")
        rows.append((y, r.classification, _score_from_result(r), r.model_name)); results_raw.append(r)
        if i % 100 == 0:
            print(f"  ... {i}/{len(pos)+len(neg)}  ({(time.perf_counter()-t0)/60:.1f} min)")

    n_pos, n_neg = len(pos), len(neg)

    preds = [_pred_positive(r) for r in results_raw]

    def summarize(tag, use_safety):
        tp = fp = fn = tn = q = 0
        for (y, clf, score, _), row_pred in zip(rows, preds):
            if use_safety and clf == "图像质量不佳":
                q += 1
                continue
            pred = (clf == "肠套叠阳性") if use_safety else row_pred
            if y == 1 and pred:
                tp += 1
            elif y == 1:
                fn += 1
            elif pred:
                fp += 1
            else:
                tn += 1
        prec = tp / max(tp + fp, 1)
        acc = (tp + tn) / max(tp + tn + fp + fn, 1)
        sens = tp / max(n_pos, 1)
        print(f"\n[{tag}]  TP={tp} FP={fp} FN={fn} TN={tn}  另判「图像质量不佳」={q}")
        print(f"[{tag}]  Precision={prec:.4f}  Accuracy={acc:.4f}  Sensitivity={sens:.4f}")
        return tp, fp, fn, tn, q

    models = {m for _, _, _, m in rows}
    print(f"\n返回的 model_name 取值: {models}")
    if any("Mock" in (m or "") for m in models):
        print("  ⚠⚠ 出现 Mock 标识 —— 真实流水线未生效，请检查两个子模块的 READY")
    else:
        print("  ✅ 全部来自真实流水线（无 Mock 标识）")

    summarize(f"当前配置（安全网{'开' if model_core.SAFETY_NET else '关'}）", True)
    summarize("等价：关掉安全网（由同一次推理的分数复原）", False)
    print(f"\n  ⏱ 总耗时 {(time.perf_counter()-t0)/60:.1f} min，平均 {(time.perf_counter()-t0)/max(1,len(rows))*1000:.0f} ms/张")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="单张图片或目录")
    ap.add_argument("--pos", nargs="*", default=None, help="批量模式：正样本目录")
    ap.add_argument("--neg", nargs="*", default=None, help="批量模式：负样本目录")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    _print_env()

    if a.pos and a.neg:
        batch(a.pos, a.neg, a.limit)
        return 0

    files = []
    for p in a.paths:
        p = Path(p)
        if p.is_dir():
            files += [f for f in sorted(p.iterdir()) if f.suffix.lower() in IMG_EXTS]
        elif p.exists():
            files.append(p)
    if not files:
        print("没有可测的图片。用法见文件头。")
        return 2
    if a.limit:
        files = files[:a.limit]

    allok = True
    for i, f in enumerate(files, 1):
        print(f"\n--- ({i}/{len(files)}) ---")
        _, ok, _ = _one(f)
        allok &= ok
    print("\n" + ("✅ 全部格式合法" if allok else "❌ 存在非法返回"))
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
