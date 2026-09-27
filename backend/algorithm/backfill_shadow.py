"""影子数据回填（推荐方式）
==============================

**为什么不走"请求内实时影子"**

实时影子（``shadow.SHADOW_ENABLED=True``）虽然只入队、不阻塞，但后台 worker 的
v2 融合推理 = 8 个模型，会和请求抢 CPU。本地 A/B 实测（Ryzen 7 5700U，CPU 推理）：

    影子关闭：请求中位 1057 ms
    影子开启：请求中位 2217 ms      → 拖慢 2.1×
    限速 3/min：仍然 +1156 ms       → 限速只降频率，不降单次争用

因此**默认关闭实时影子**，改用本脚本对**已存盘的影像**做批量回填：
零延迟影响、可随时中断/续跑、也不需要服务在线。

**用法**

    # 回填平台已上传的全部影像（默认目录取自 backend/config.py 的 UPLOAD_DIR）
    python -m algorithm.backfill_shadow

    # 指定目录、限量试跑
    python -m algorithm.backfill_shadow --images D:\\some\\images --limit 20

    # 若整批图已知都是阴性（例如正常样本池），可顺手打标，省掉人工标注
    python -m algorithm.backfill_shadow --images D:\\normal --assume-label 0

    # 看进度 / ETA
    python -m algorithm.backfill_shadow --status

回填记录与实时影子写入**同一个** ``shadow_data/shadow.jsonl``（按图像 md5 去重、可续跑），
因此 ``calibrate_shadow.py`` 不需要任何改动。

建议用 Windows 计划任务 / cron 每晚跑一次；影像只会越攒越多，而标定只需要无偏负样本。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import numpy as np  # noqa: E402

from algorithm import model_core, shadow  # noqa: E402

IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".dcm")


def default_upload_dir() -> Path:
    try:
        sys.path.insert(0, str(BACKEND))
        from config import UPLOAD_DIR  # type: ignore
        return Path(UPLOAD_DIR)
    except Exception:
        return BACKEND.parent / "uploads"


def load_done() -> set:
    p = shadow.SHADOW_DIR / "shadow.jsonl"
    done = set()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["md5"])
            except Exception:
                continue
    return done


def load_image_bgr(path: Path):
    from algorithm.pipeline import load_image
    try:
        return model_core.to_bgr(load_image(path))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="*", default=None, help="要回填的目录或文件（默认平台 UPLOAD_DIR）")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--policy", default=shadow.SHADOW_POLICY)
    ap.add_argument("--assume-label", choices=["0", "1"], default=None,
                    help="若整批图的真值已知（如全是阴性），直接写入 labels.csv")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    shadow.SHADOW_DIR.mkdir(parents=True, exist_ok=True)
    if shadow.SHADOW_SAVE_IMAGES:
        (shadow.SHADOW_DIR / "images").mkdir(parents=True, exist_ok=True)

    if a.status:
        done = load_done()
        p = shadow.SHADOW_DIR / "shadow.jsonl"
        print(f"影子数据目录 : {shadow.SHADOW_DIR}")
        print(f"已回填(去重) : {len(done)} 张")
        print(f"文件         : {p}  ({p.stat().st_size if p.exists() else 0} 字节)")
        lab = shadow.SHADOW_DIR / "labels.csv"
        if lab.exists():
            n = sum(1 for line in lab.read_text(encoding="utf-8-sig").splitlines()[1:] if line.strip())
            print(f"待标注清单   : {lab}  ({n} 行)")
        return 0

    roots = [Path(x) for x in (a.images or [default_upload_dir()])]
    files = []
    for r in roots:
        if r.is_dir():
            files += [f for f in sorted(r.rglob("*")) if f.is_file() and f.suffix.lower() in IMG_EXTS]
        elif r.exists():
            files.append(r)
    if not files:
        print(f"[提示] 没有找到影像。检查目录：{[str(r) for r in roots]}")
        return 2

    done = load_done()
    todo = []
    t0 = time.time()
    for f in files:
        if a.limit and len(todo) >= a.limit:
            break
        try:
            raw = f.read_bytes()
        except Exception:
            continue
        if hashlib.md5(raw).hexdigest() in done:       # 文件级去重（图片级 md5 在下方判断）
            pass
        todo.append(f)

    print(f"候选 {len(todo)} 张（已回填 {len(done)} 张）；策略 {a.policy}")
    from algorithm import classification  # noqa: F401  触发日志
    model_core._resolve(a.policy, enforce_deploy_guard=False)

    n_ok = n_skip = n_fail = 0
    labels = {}
    for i, f in enumerate(todo, 1):
        bgr = load_image_bgr(f)
        if bgr is None or min(bgr.shape[:2]) < model_core.MIN_SIDE:
            n_fail += 1
            continue
        key = hashlib.md5(np.ascontiguousarray(bgr).tobytes()).hexdigest()
        if key in done:
            n_skip += 1
            continue
        try:
            deployed = model_core.score_with(model_core.POLICY, bgr, enforce_deploy_guard=True)
            cand = model_core.score_with(a.policy, bgr, enforce_deploy_guard=False)
        except Exception as exc:
            n_fail += 1
            print(f"  [失败] {f.name}: {exc}")
            continue
        deployed_thr = float(model_core.POLICIES[model_core.POLICY]["threshold"])
        deployed_label = "肠套叠阳性" if deployed["score"] >= deployed_thr else "肠套叠阴性"
        if shadow.SHADOW_SAVE_IMAGES:
            p = shadow.SHADOW_DIR / "images" / f"{key}.jpg"
            if not p.exists():
                import cv2
                ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), shadow.SHADOW_JPEG_QUALITY])
                if ok:
                    buf.tofile(str(p))
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "md5": key, "h": int(bgr.shape[0]),
               "w": int(bgr.shape[1]), "black_ratio": round(model_core.black_ratio(bgr), 5),
               "deployed_score": round(float(deployed["score"]), 8), "deployed_label": deployed_label,
               "shadow_policy": a.policy, "shadow_version": cand["version"],
               "shadow_score": round(float(cand["score"]), 8),
               "shadow_threshold_placeholder": round(float(cand["threshold"]), 8),
               "image": f"images/{key}.jpg" if shadow.SHADOW_SAVE_IMAGES else None,
               "source": str(f)}
        with open(shadow.SHADOW_DIR / "shadow.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        done.add(key)
        if a.assume_label is not None:
            labels[key] = int(a.assume_label)
        n_ok += 1
        if i % 25 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"  {i}/{len(todo)}  成功{n_ok} 跳过{n_skip} 失败{n_fail}  "
                  f"{(el/i):.2f}s/张  ETA {(len(todo)-i)*el/i/60:.1f} min")

    if labels:
        lab_path = shadow.SHADOW_DIR / "labels.csv"
        exist = {}
        if lab_path.exists():
            with open(lab_path, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    exist[row["md5"]] = row.get("label", "")
        exist.update({k: str(v) for k, v in labels.items()})
        with open(lab_path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh); w.writerow(["md5", "label"])
            for k, v in exist.items():
                w.writerow([k, v])
        print(f"已写入 {len(labels)} 条已知标签 -> {lab_path}")

    print(f"\n完成：新增 {n_ok}，跳过(已存在) {n_skip}，失败 {n_fail}，用时 {(time.time()-t0)/60:.1f} min")
    print(f"累计去重 {len(done)} 张。下一步：python -m algorithm.calibrate_shadow --export")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
