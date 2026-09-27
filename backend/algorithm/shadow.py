"""候选模型标定数据采集（Shadow data collection）
====================================================

**它解决什么问题**

``v2``（候选策略）的判别力明显更好，但它的**判定阈值还没有一个合法来源**：

* 用训练期用过的负样本标定 → 这些图模型见过（样本内），分数被系统性压低，
  标定出的阈值偏低，直接沿用会让 Precision 掉到 0.9307（<95%）；
* 用交叉验证的折外分数标定 → 已做过预验证并否定：即便校准集无偏，
  留出样本上的双 95% 达成率也只有 50–53%，"按最大 Acc 选阈值"这类规则
  在小样本上是负收益（用 339 张无偏数据当校准集时，现部署策略的 Acc 从 0.9528 掉到 0.9499）。

**因此改用影子采集**：真实流量里累积的负样本是**真正无偏**的（模型从没见过它们），
比折外分数更干净，而且不需要任何 GPU。

**它怎么工作**

    classification.classify() 判完（决策仍由 v1 + 安全网给出）
        └─ shadow.submit(bgr, v1_score, v1_label)   ← 只入队，立刻返回，不阻塞请求
              └─ 后台单线程 worker：用 v2 策略算一遍融合分数
                    └─ 追加写入 shadow_data/shadow.jsonl，并把图像存成 shadow_data/images/<md5>.jpg

要点：
* **决策完全不受影响** —— 影子分数不参与任何返回字段；
* **不拖慢请求** —— 入队即返回；队列满则丢弃（影子数据允许 best-effort）；
* 图像按 md5 去重，同一张只存一份；可通过 ``SHADOW_SAVE_IMAGES`` 关闭存图；
* 权重缺失或环境异常时**自动禁用**并记一条日志，绝不影响主链路。

标定工具见 ``algorithm/calibrate_shadow.py``。
"""
from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from algorithm import model_core

logger = logging.getLogger("uvicorn.error")

# --------------------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------------------
# ★ 默认关闭：实时影子虽不阻塞请求，但后台 v2 融合推理（8 个模型）会和请求抢 CPU。
#   本地 A/B 实测（CPU 推理）：请求中位 1057 ms → 2217 ms（**拖慢 2.1×**）；
#   加限速（3/min）后仍有 +1156 ms —— 限速只降频率、不降单次争用。
#   → **推荐用 algorithm/backfill_shadow.py 对已存盘影像做批量回填（零延迟影响）**。
#   只有在服务有余量（例如 GPU 部署、影子可排队）时才把这里改成 True。
SHADOW_ENABLED = False
SHADOW_POLICY = "v2"                      # 要标定的候选策略
SHADOW_DIR = Path(os.environ.get("ALGO_SHADOW_DIR", str(model_core.ALGO_DIR / "shadow_data")))
SHADOW_QUEUE_MAX = 64                        # 队列上限；满了就丢（影子数据 best-effort）
SHADOW_SAVE_IMAGES = True                    # 是否把图像存一份以便后续复核
SHADOW_JPEG_QUALITY = 85

# 若启用实时影子，下面三个是限速/采样旋钮（SHADOW_MAX_PER_MINUTE=0 表示不限速）
SHADOW_MAX_PER_MINUTE = 6                    # 每分钟最多处理几张
SHADOW_SAMPLE_RATE = 1.0                     # 命中限速前先按比例采样（1.0=全采）
SHADOW_IDLE_SLEEP = 0.05                     # worker 空转间隔，避免忙等抢 CPU

_QUEUE: "queue.Queue[Optional[tuple]]" = queue.Queue(maxsize=SHADOW_QUEUE_MAX)
_STARTED = False
_START_LOCK = threading.Lock()
_STOP = threading.Event()
_STATS = {"submitted": 0, "scored": 0, "dropped": 0, "failed": 0}


def available() -> tuple:
    """影子模式是否可用 → (ok, reason)。"""
    if not SHADOW_ENABLED:
        return False, "SHADOW_ENABLED=False"
    try:
        model_core._resolve(SHADOW_POLICY, enforce_deploy_guard=False)
    except Exception as exc:
        return False, f"候选策略 {SHADOW_POLICY} 不可用：{exc}"
    return True, "ok"


# --------------------------------------------------------------------------------------
# 后台 worker
# --------------------------------------------------------------------------------------
def _ensure_started() -> None:
    global _STARTED
    if _STARTED:
        return
    with _START_LOCK:
        if _STARTED:
            return
        SHADOW_DIR.mkdir(parents=True, exist_ok=True)
        if SHADOW_SAVE_IMAGES:
            (SHADOW_DIR / "images").mkdir(parents=True, exist_ok=True)
        t = threading.Thread(target=_worker, name="algo-shadow", daemon=True)
        t.start()
        _STARTED = True
        ok, why = available()
        logger.info("[影子模式] 已启用 candidate=%s 目录=%s 可用=%s(%s)",
                    SHADOW_POLICY, SHADOW_DIR, ok, why)


def _sha1(bgr: np.ndarray) -> str:
    return hashlib.md5(np.ascontiguousarray(bgr).tobytes()).hexdigest()


def _worker() -> None:
    while not _STOP.is_set():
        try:
            item = _QUEUE.get(timeout=SHADOW_IDLE_SLEEP)
        except queue.Empty:
            continue
        if item is None:
            break
        bgr, deployed_score, deployed_label, ts = item
        t_start = time.time()
        try:
            res = model_core.score_with(SHADOW_POLICY, bgr)
            key = _sha1(bgr)
            rel_img = None
            if SHADOW_SAVE_IMAGES:
                p = SHADOW_DIR / "images" / f"{key}.jpg"
                if not p.exists():
                    ok, buf = __import__("cv2").imencode(
                        ".jpg", bgr, [int(__import__("cv2").IMWRITE_JPEG_QUALITY), SHADOW_JPEG_QUALITY])
                    if ok:
                        buf.tofile(str(p))
                rel_img = f"images/{key}.jpg"
            rec = {
                "ts": ts,
                "md5": key,
                "h": int(bgr.shape[0]),
                "w": int(bgr.shape[1]),
                "black_ratio": round(model_core.black_ratio(bgr), 5),
                "deployed_score": round(float(deployed_score), 8),
                "deployed_label": deployed_label,
                "shadow_policy": SHADOW_POLICY,
                "shadow_version": res["version"],
                "shadow_score": round(float(res["score"]), 8),
                "shadow_threshold_placeholder": round(float(res["threshold"]), 8),
                "image": rel_img,
            }
            with open(SHADOW_DIR / "shadow.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            _STATS["scored"] += 1
        except Exception as exc:  # 影子链路绝不能影响主链路
            _STATS["failed"] += 1
            logger.warning("[影子模式] 打分失败（已忽略）：%s", exc)
        finally:
            _QUEUE.task_done()
            # ★ 限速：把空闲时间补回去，避免影子推理持续吃满 CPU 拖慢线上请求
            if SHADOW_MAX_PER_MINUTE and SHADOW_MAX_PER_MINUTE > 0:
                budget = 60.0 / SHADOW_MAX_PER_MINUTE
                gap = budget - (time.time() - t_start)
                if gap > 0:
                    _STOP.wait(gap)


def _shutdown() -> None:
    _STOP.set()
    try:
        _QUEUE.put_nowait(None)
    except Exception:
        pass


atexit.register(_shutdown)


# --------------------------------------------------------------------------------------
# 对外接口
# --------------------------------------------------------------------------------------
def submit(bgr: Any, deployed_score: Optional[float], deployed_label: str) -> bool:
    """把一次请求投递给影子 worker。**立即返回**，不影响主链路。返回是否成功入队。"""
    if not SHADOW_ENABLED or bgr is None:
        return False
    _STATS["submitted"] += 1
    try:
        arr = np.ascontiguousarray(bgr)          # 复制一份，避免调用方后续改动
    except Exception:
        return False
    try:
        _ensure_started()
        _QUEUE.put_nowait((arr, deployed_score, deployed_label, time.strftime("%Y-%m-%d %H:%M:%S")))
        return True
    except queue.Full:
        _STATS["dropped"] += 1
        return False
    except Exception as exc:
        _STATS["failed"] += 1
        logger.warning("[影子模式] 入队失败（已忽略）：%s", exc)
        return False


def stats() -> dict:
    ok, why = available()
    return {**_STATS, "enabled": SHADOW_ENABLED, "candidate": SHADOW_POLICY,
            "dir": str(SHADOW_DIR), "available": ok, "reason": why,
            "queue_size": _QUEUE.qsize(), "started": _STARTED}


def flush(timeout: float = 30.0) -> bool:
    """等队列跑空（关服务或批量评测后调用，确保数据落盘）。"""
    t0 = time.time()
    while _QUEUE.unfinished_tasks > 0 and time.time() - t0 < timeout:
        time.sleep(0.2)
    return _QUEUE.unfinished_tasks == 0
