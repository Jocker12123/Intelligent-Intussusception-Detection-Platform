"""异步检测任务管理器（单进程内网部署用）。

提供一个轻量、基于内存的任务注册表 + 后台线程执行，避免真实模型推理时阻塞 HTTP 请求。
- 任务在独立线程中运行，使用自己打开的数据库会话（与请求会话隔离）。
- 状态机: pending -> running -> done | failed
- 任务存活于进程内存，进程重启后丢失（内网单进程场景可接受）。

注意：并发写 SQLite 由 SQLite 自身锁保证；此处限制每个进程仅单线程后台执行，
避免多个模型实例同时跑导致资源争抢。
"""
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from database import SessionLocal
from models import Image
from services.detection import DetectionService


@dataclass
class DetectionTask:
    id: str
    image_id: int
    status: str = "pending"          # pending | running | done | failed
    progress: int = 0                # 0-100，尽力估算
    result_id: Optional[int] = None  # 完成后的结果 ID
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class DetectionTaskManager:
    """进程内任务注册表，单例使用。"""

    def __init__(self) -> None:
        self._tasks: dict[str, DetectionTask] = {}
        self._lock = threading.Lock()

    def _get(self, task_id: str) -> Optional[DetectionTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def get(self, task_id: str) -> Optional[DetectionTask]:
        return self._get(task_id)

    def submit(self, image_id: int) -> DetectionTask:
        """提交一个检测任务，立刻返回。实际检测在后台线程执行。"""
        task = DetectionTask(id=uuid.uuid4().hex[:12], image_id=image_id)
        with self._lock:
            self._tasks[task.id] = task
        threading.Thread(target=self._run, args=(task.id, image_id), daemon=True).start()
        return task

    def _run(self, task_id: str, image_id: int) -> None:
        task = self._get(task_id)
        if task is None:
            return
        task.status = "running"
        task.started_at = time.time()
        task.progress = 10
        # 单个后台线程串行执行，避免多实例争抢资源
        db = SessionLocal()
        try:
            image = db.query(Image).filter(Image.id == image_id).first()
            if image is None:
                task.progress = 100
                task.status = "failed"
                task.error = "影像不存在"
                return
            task.progress = 30
            result = DetectionService.run_detection(image, db)
            task.progress = 90
            task.result_id = result.id
            task.progress = 100
            task.status = "done"
        except Exception as exc:  # noqa: BLE001
            task.status = "failed"
            task.error = f"检测失败: {exc}"
            traceback.print_exc()
        finally:
            task.finished_at = time.time()
            db.close()


_manager = DetectionTaskManager()


def get_task(task_id: str) -> Optional[DetectionTask]:
    return _manager.get(task_id)


def submit_detection_task(image_id: int) -> DetectionTask:
    return _manager.submit(image_id)
