"""算法标注图（带病灶框）落盘与展示的测试。

覆盖：
  1. save_result_image 支持 bytes / 文件路径，拒绝非法输入
  2. remove_result_image 只删标注图目录内的文件
  3. 检测接口回传 has_result_image，并能取到标注图
  4. 重新检测会清掉旧的标注图文件（不留孤儿文件）
"""
import io
from pathlib import Path

import pytest

from services import result_images

# 一张最小的合法 JPEG（与 test_results.py 中用的字节一致，仅用于魔数校验）
JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n"
    b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x22\x00\x02\x11\x01\x03"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf\x20\xff\xd9"
)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def temp_result_dir(tmp_path, monkeypatch):
    """把标注图目录指到临时目录，避免污染真实 uploads/。"""
    monkeypatch.setattr(result_images, "RESULT_IMAGE_DIR", str(tmp_path / "results"))
    yield tmp_path / "results"


def test_save_bytes_keeps_format(temp_result_dir):
    path = result_images.save_result_image(7, JPEG_BYTES)
    assert path.endswith(".jpg")
    assert Path(path).exists()
    assert Path(path).parent == temp_result_dir
    assert Path(path).read_bytes() == JPEG_BYTES

    png_path = result_images.save_result_image(7, PNG_BYTES)
    assert png_path.endswith(".png")


def test_save_from_file_path(temp_result_dir, tmp_path):
    src = tmp_path / "annotated.png"
    src.write_bytes(PNG_BYTES)
    saved = result_images.save_result_image(3, str(src))
    assert saved.endswith(".png")
    assert saved != str(src)          # 复制而非引用，平台自己管理生命周期


def test_save_rejects_bad_payload(temp_result_dir, tmp_path):
    with pytest.raises(ValueError):
        result_images.save_result_image(1, b"not an image at all")
    with pytest.raises(ValueError):
        result_images.save_result_image(1, str(tmp_path / "missing.jpg"))
    with pytest.raises(TypeError):
        result_images.save_result_image(1, 12345)


def test_remove_only_inside_result_dir(temp_result_dir, tmp_path):
    saved = Path(result_images.save_result_image(5, JPEG_BYTES))
    result_images.remove_result_image(str(saved))
    assert not saved.exists()

    # 目录外的文件不应被删除
    outsider = tmp_path / "keep.jpg"
    outsider.write_bytes(JPEG_BYTES)
    result_images.remove_result_image(str(outsider))
    assert outsider.exists()

    # 空值 / 不存在的路径不应报错
    result_images.remove_result_image(None)
    result_images.remove_result_image(str(temp_result_dir / "nope.jpg"))


def _upload(client, auth_headers):
    pid = client.post("/api/patients", json={"name": "标注图", "gender": "Male", "age": 12},
                      headers=auth_headers).json()["id"]
    up = client.post(
        "/api/images/upload",
        files={"file": ("r.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        data={"patient_id": str(pid)},
        headers=auth_headers,
    )
    return pid, up.json()["id"]


def test_detection_with_annotated_image_end_to_end(client, auth_headers, monkeypatch, temp_result_dir):
    """算法回传标注图时：结果标记 has_result_image，且取图接口能拿到它。"""
    from algorithm.interface import DetectionResult
    from services import detection as detection_service

    _, img_id = _upload(client, auth_headers)

    def fake_detect(_path):
        return DetectionResult(
            classification="肠套叠阳性",
            confidence=0.91,
            detection_model_name="DetA",
            detection_model_version="1.0.0",
            classification_model_name="ClsB",
            roi_box=(1, 1, 1, 1),
            result_image=PNG_BYTES,
        )

    monkeypatch.setattr(detection_service, "detect_intussusception", fake_detect)

    resp = client.post(f"/api/images/{img_id}/detect", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_result_image"] is True
    assert body["detection_model_name"] == "DetA"
    assert body["classification_model_name"] == "ClsB"
    assert body["roi_box"] == [1, 1, 1, 1]

    img_resp = client.get(f"/api/results/{body['id']}/image", headers=auth_headers)
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"].startswith("image/png")
    assert img_resp.content == PNG_BYTES


def test_detection_without_annotated_image_returns_404(client, auth_headers):
    """没回传标注图（当前 Mock 情况）：标记为 False，取图接口 404。"""
    _, img_id = _upload(client, auth_headers)
    body = client.post(f"/api/images/{img_id}/detect", headers=auth_headers).json()
    assert body["has_result_image"] is False
    assert client.get(f"/api/results/{body['id']}/image", headers=auth_headers).status_code == 404


def test_redetect_removes_previous_annotated_image(client, auth_headers, monkeypatch, temp_result_dir):
    """重新检测（force）时应清掉上一次的标注图，避免磁盘上留孤儿文件。"""
    from algorithm.interface import DetectionResult
    from services import detection as detection_service

    _, img_id = _upload(client, auth_headers)
    monkeypatch.setattr(detection_service, "detect_intussusception", lambda _p: DetectionResult(
        classification="肠套叠阳性", confidence=0.9, result_image=PNG_BYTES,
    ))

    first = client.post(f"/api/images/{img_id}/detect", headers=auth_headers).json()
    assert first["has_result_image"] is True
    assert len(list(temp_result_dir.iterdir())) == 1

    second = client.post(f"/api/images/{img_id}/detect?force=true", headers=auth_headers).json()
    assert second["has_result_image"] is True
    # 旧文件被删、新文件落盘，而不是越攒越多
    assert len(list(temp_result_dir.iterdir())) == 1


def test_bad_annotated_image_does_not_lose_diagnosis(client, auth_headers, monkeypatch):
    """标注图存不下来时，诊断结果仍要正常入库（只是没有标注图）。"""
    from algorithm.interface import DetectionResult
    from services import detection as detection_service

    _, img_id = _upload(client, auth_headers)
    monkeypatch.setattr(detection_service, "detect_intussusception", lambda _p: DetectionResult(
        classification="肠套叠阴性", confidence=0.8, result_image=b"garbage-not-an-image",
    ))

    resp = client.post(f"/api/images/{img_id}/detect", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["classification"] == "肠套叠阴性"
    assert resp.json()["has_result_image"] is False
