"""标注图存盘服务
=================

算法（检测模块 A）可以在 `DetectionResult.result_image` 里回传**带病灶框的标注图**，
本模块负责把它落盘、给出路径，并在结果被覆盖/删除时清理旧文件。

支持的三种回传形态（由 `save_result_image` 统一处理）:
    1) bytes / bytearray   —— 已编码的 JPEG/PNG/BMP 字节（推荐：算法侧零额外依赖）
    2) str / Path          —— 算法自己写好的图片文件路径（会被复制到平台目录）
    3) numpy.ndarray       —— H×W 或 H×W×3 数组（需要安装 pillow，否则给出明确报错）

存盘位置：`<UPLOAD_DIR>/results/`，文件名 `result_<影像ID>_<随机串>.<ext>`，
与原始上传影像分开存放，避免和 `uploads/` 根目录下的原图混在一起。
"""
import logging
import os
import uuid
from pathlib import Path

from config import MAX_UPLOAD_SIZE, UPLOAD_DIR

logger = logging.getLogger("uvicorn.error")

# 标注图存放目录（随 UPLOAD_DIR 配置一起走，测试里可被覆盖）
RESULT_IMAGE_DIR = os.path.join(UPLOAD_DIR, "results")

# 允许的图片字节魔数 → 存盘后缀
_MAGIC_TO_EXT = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"BM", ".bmp"),
    (b"RIFF", ".webp"),          # RIFF....WEBP，下面再做二次确认
)


def ensure_result_image_dir() -> str:
    os.makedirs(RESULT_IMAGE_DIR, exist_ok=True)
    return RESULT_IMAGE_DIR


def _guess_ext(data: bytes) -> str | None:
    """按文件真实字节判断图片格式，返回后缀；不是支持的图片格式则返回 None。"""
    for magic, ext in _MAGIC_TO_EXT:
        if data.startswith(magic):
            if ext == ".webp" and data[8:12] != b"WEBP":
                continue
            return ext
    return None


def _encode_ndarray(array) -> bytes:
    """把 numpy 数组编码成 PNG 字节（需要 pillow）。"""
    try:
        from PIL import Image  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "算法回传了 numpy 数组形式的标注图，但环境未安装 Pillow。"
            "请执行 `pip install pillow` 并写入 requirements.txt，"
            "或改为回传已编码的图片字节（bytes）。"
        ) from exc

    import io  # noqa: WPS433

    img = Image.fromarray(array)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _to_image_bytes(payload) -> bytes:
    """把算法回传的三种形态统一成图片字节。"""
    # 1) 已编码字节
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload)

    # 2) 文件路径
    if isinstance(payload, (str, os.PathLike)):
        path = Path(payload)
        if not path.is_file():
            raise ValueError(f"result_image 指向的文件不存在：{payload}")
        data = path.read_bytes()
        if not _guess_ext(data):
            raise ValueError(f"result_image 指向的文件不是支持的图片格式：{payload}")
        return data

    # 3) numpy 数组（不直接 import numpy，避免平台强依赖）
    if hasattr(payload, "tobytes") and hasattr(payload, "shape"):
        return _encode_ndarray(payload)

    raise TypeError(
        "result_image 只支持 bytes / 图片文件路径 / numpy.ndarray，"
        f"收到的是 {type(payload).__name__}"
    )


def save_result_image(image_id: int, payload) -> str:
    """保存算法回传的标注图，返回存盘绝对路径。

    参数非法（类型不对、文件不存在、字节不是图片、体积超限）时抛异常，
    由调用方决定是否忽略——**绝不能因为标注图存不下来就丢掉诊断结果**。
    """
    data = _to_image_bytes(payload)
    if len(data) > MAX_UPLOAD_SIZE:
        raise ValueError(f"标注图体积过大（{len(data)} 字节，上限 {MAX_UPLOAD_SIZE}）")
    ext = _guess_ext(data)
    if not ext:
        raise ValueError("标注图内容无法识别，请回传 JPG/PNG/BMP/WEBP 图片")

    directory = ensure_result_image_dir()
    filename = f"result_{image_id}_{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(directory, filename)
    with open(stored_path, "wb") as f:
        f.write(data)
    logger.info("已保存算法标注图：%s（%d 字节）", stored_path, len(data))
    return stored_path


def remove_result_image(stored_path: str | None) -> None:
    """删除标注图文件（仅限标注图目录内，避免误删其它文件）。"""
    if not stored_path:
        return
    try:
        target = Path(stored_path).resolve()
        directory = Path(ensure_result_image_dir()).resolve()
        if directory not in target.parents:
            logger.warning("拒绝删除标注图目录外的文件：%s", stored_path)
            return
        if target.is_file():
            target.unlink()
    except OSError as exc:  # pragma: no cover
        logger.warning("删除标注图失败：%s（%s）", stored_path, exc)


def image_media_type(stored_path: str) -> str:
    """按后缀给出标注图的媒体类型。"""
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".bmp": "image/bmp", ".webp": "image/webp",
    }.get(Path(stored_path).suffix.lower(), "application/octet-stream")


__all__ = [
    "RESULT_IMAGE_DIR",
    "ensure_result_image_dir",
    "save_result_image",
    "remove_result_image",
    "image_media_type",
]
