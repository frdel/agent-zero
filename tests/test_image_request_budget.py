from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers import images


def _write_noisy_jpeg(path: Path, size: tuple[int, int] = (3000, 2000), quality: int = 95) -> None:
    data = os.urandom(size[0] * size[1] * 3)
    Image.frombytes("RGB", size, data).save(path, format="JPEG", quality=quality)


def _decoded_size(data_url: str) -> int:
    return len(base64.b64decode(data_url.split(",", 1)[1]))


def _refs(count: int) -> list[dict]:
    return [
        {"type": "image_url", "image_url": {"url": "/tmp/budget-probe.png"}}
        for _ in range(count)
    ]


def test_to_data_url_caps_oversized_images(tmp_path):
    path = tmp_path / "huge.jpg"
    _write_noisy_jpeg(path)
    assert path.stat().st_size > images.IMAGE_INLINE_MAX_BYTES

    data_url = images.to_data_url(str(path), max_bytes=300_000)

    assert data_url.startswith("data:image/jpeg;base64,")
    assert _decoded_size(data_url) <= 300_000


def test_to_data_url_leaves_small_images_untouched(tmp_path):
    path = tmp_path / "small.jpg"
    Image.new("RGB", (64, 64), (10, 20, 30)).save(path, format="JPEG", quality=90)
    original = path.read_bytes()

    data_url = images.to_data_url(str(path))

    assert base64.b64decode(data_url.split(",", 1)[1]) == original


def test_image_budget_scales_with_reference_count():
    assert images.image_budget_for([{"type": "text", "text": "hello"}]) is None
    assert images.count_local_refs(_refs(1)[0]) == 1
    assert images.image_budget_for(_refs(1)) == images.IMAGE_INLINE_MAX_BYTES
    assert images.image_budget_for(_refs(20)) == images.IMAGE_BUDGET_FLOOR_BYTES
    assert images.image_budget_for(_refs(5)) == images.IMAGE_REQUEST_BUDGET_BYTES // 5
