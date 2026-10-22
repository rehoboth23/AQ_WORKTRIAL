#!/usr/bin/env python3
"""Generate the thumbgen package with broken Pillow 10.x references."""
import os

BASE = "/app/thumbgen"
PKG = os.path.join(BASE, "thumbgen")
TESTS = os.path.join(BASE, "tests")

os.makedirs(PKG, exist_ok=True)
os.makedirs(TESTS, exist_ok=True)

# ── pyproject.toml ──────────────────────────────────────────────────────────
with open(os.path.join(BASE, "pyproject.toml"), "w") as f:
    f.write("""\
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "thumbgen"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = ["Pillow>=10.0"]

[tool.setuptools.packages.find]
where = ["."]

[tool.pytest.ini_options]
testpaths = ["tests"]
""")

# ── thumbgen/__init__.py ────────────────────────────────────────────────────
with open(os.path.join(PKG, "__init__.py"), "w") as f:
    f.write("""\
from .resizer import resize_exact, resize_proportional, resize_to_fill
from .watermark import apply_text_watermark
from .optimizer import optimize_for_web

__all__ = [
    "resize_exact",
    "resize_proportional",
    "resize_to_fill",
    "apply_text_watermark",
    "optimize_for_web",
]
""")

# ── thumbgen/compat.py ──────────────────────────────────────────────────────
# Partially migrated: RESAMPLE_* constants use the new API,
# but QUALITY_MAP still references the removed Image.ANTIALIAS.
with open(os.path.join(PKG, "compat.py"), "w") as f:
    f.write("""\
from PIL import Image

# Migrated constants (using new Pillow 10 API)
RESAMPLE_HIGH = Image.Resampling.LANCZOS
RESAMPLE_MED = Image.Resampling.BILINEAR
RESAMPLE_LOW = Image.Resampling.NEAREST

# Quality map for convenience lookups
QUALITY_MAP = {
    "high": Image.ANTIALIAS,
    "medium": RESAMPLE_MED,
    "low": RESAMPLE_LOW,
}


def get_resample_method(quality="high"):
    return QUALITY_MAP.get(quality, RESAMPLE_HIGH)
""")

# ── thumbgen/resizer.py ─────────────────────────────────────────────────────
# Default parameter in resize_exact still uses the removed Image.ANTIALIAS.
with open(os.path.join(PKG, "resizer.py"), "w") as f:
    f.write("""\
from PIL import Image
from .compat import get_resample_method


def resize_exact(image, width, height, method=Image.ANTIALIAS):
    return image.resize((width, height), method)


def resize_proportional(image, max_dimension, quality="high"):
    method = get_resample_method(quality)
    ratio = min(max_dimension / image.width, max_dimension / image.height)
    new_w = int(image.width * ratio)
    new_h = int(image.height * ratio)
    return image.resize((new_w, new_h), method)


def resize_to_fill(image, width, height, quality="high"):
    method = get_resample_method(quality)
    ratio = max(width / image.width, height / image.height)
    resized = image.resize(
        (int(image.width * ratio), int(image.height * ratio)), method
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))
""")

# ── thumbgen/watermark.py ───────────────────────────────────────────────────
# thumbnail call inside apply_text_watermark uses Image.ANTIALIAS.
with open(os.path.join(PKG, "watermark.py"), "w") as f:
    f.write("""\
import os
from PIL import Image, ImageDraw, ImageFont


def apply_text_watermark(image, text, opacity=128, position="bottom-right"):
    image = image.convert("RGBA")

    # Use thumbnail to determine proportional font size
    thumb = image.copy()
    thumb.thumbnail((200, 200), Image.ANTIALIAS)
    font_size = max(12, int(thumb.width / 10))

    font = None
    for fp in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
            except Exception:
                font = None
            break
    if font is None:
        font = ImageFont.load_default()

    watermark_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad = 10
    if position == "bottom-right":
        x, y = image.width - text_w - pad, image.height - text_h - pad
    elif position == "bottom-left":
        x, y = pad, image.height - text_h - pad
    elif position == "top-right":
        x, y = image.width - text_w - pad, pad
    else:
        x, y = pad, pad

    draw.text((x, y), text, fill=(255, 255, 255, opacity), font=font)
    return Image.alpha_composite(image, watermark_layer)
""")

# ── thumbgen/optimizer.py ───────────────────────────────────────────────────
# JPEG branch uses compat (migrated), but PNG branch uses Image.ANTIALIAS directly.
with open(os.path.join(PKG, "optimizer.py"), "w") as f:
    f.write("""\
from PIL import Image
from .compat import get_resample_method


def optimize_for_web(image, format="JPEG", max_size=(200, 200)):
    if format.upper() == "JPEG":
        method = get_resample_method("high")
        thumb = image.copy()
        thumb.thumbnail(max_size, method)
        return thumb
    elif format.upper() == "PNG":
        result = {}
        sizes = {"small": (100, 100), "medium": (200, 200), "large": (400, 400)}
        for name, size in sizes.items():
            thumb = image.copy()
            thumb.thumbnail(size, Image.ANTIALIAS)
            result[name] = thumb
        return result
    else:
        raise ValueError(f"Unsupported format: {format}")
""")

# ── tests/__init__.py ───────────────────────────────────────────────────────
with open(os.path.join(TESTS, "__init__.py"), "w") as f:
    f.write("")

# ── tests/conftest.py ───────────────────────────────────────────────────────
with open(os.path.join(TESTS, "conftest.py"), "w") as f:
    f.write("""\
import pytest
from PIL import Image


@pytest.fixture
def sample_image():
    return Image.new("RGB", (400, 300), color=(100, 150, 200))


@pytest.fixture
def large_image():
    return Image.new("RGB", (800, 600), color=(50, 100, 150))
""")

# ── tests/test_compat.py ────────────────────────────────────────────────────
with open(os.path.join(TESTS, "test_compat.py"), "w") as f:
    f.write("""\
from PIL import Image
from thumbgen.compat import get_resample_method, RESAMPLE_HIGH, RESAMPLE_MED, RESAMPLE_LOW


def test_resample_constants():
    assert RESAMPLE_HIGH == Image.Resampling.LANCZOS
    assert RESAMPLE_MED == Image.Resampling.BILINEAR
    assert RESAMPLE_LOW == Image.Resampling.NEAREST


def test_get_resample_method():
    assert get_resample_method("high") == Image.Resampling.LANCZOS
    assert get_resample_method("medium") == Image.Resampling.BILINEAR
    assert get_resample_method("low") == Image.Resampling.NEAREST
""")

# ── tests/test_resizer.py ───────────────────────────────────────────────────
with open(os.path.join(TESTS, "test_resizer.py"), "w") as f:
    f.write("""\
from PIL import Image
from thumbgen.resizer import resize_exact, resize_proportional, resize_to_fill


def test_resize_exact(sample_image):
    result = resize_exact(sample_image, 200, 150)
    assert result.size == (200, 150)


def test_resize_proportional(sample_image):
    result = resize_proportional(sample_image, max_dimension=200, quality="high")
    assert result.width <= 200
    assert result.height <= 200
    ratio = result.width / result.height
    assert abs(ratio - 4 / 3) < 0.1


def test_resize_to_fill(sample_image):
    result = resize_to_fill(sample_image, 200, 200, quality="high")
    assert result.size == (200, 200)
""")

# ── tests/test_watermark.py ─────────────────────────────────────────────────
with open(os.path.join(TESTS, "test_watermark.py"), "w") as f:
    f.write("""\
from PIL import Image
from thumbgen.watermark import apply_text_watermark


def test_apply_text_watermark(sample_image):
    result = apply_text_watermark(sample_image, "TEST")
    assert result.size == (400, 300)
    assert result.mode == "RGBA"


def test_watermark_opacity(sample_image):
    result = apply_text_watermark(sample_image, "WATERMARK", opacity=200)
    assert result.mode == "RGBA"
""")

# ── tests/test_optimizer.py ─────────────────────────────────────────────────
with open(os.path.join(TESTS, "test_optimizer.py"), "w") as f:
    f.write("""\
from PIL import Image
from thumbgen.optimizer import optimize_for_web


def test_optimize_jpeg(large_image):
    result = optimize_for_web(large_image, format="JPEG")
    assert result.size[0] <= 200
    assert result.size[1] <= 200


def test_optimize_png(large_image):
    result = optimize_for_web(large_image, format="PNG")
    assert "small" in result
    assert "medium" in result
    assert "large" in result
    assert result["small"].size[0] <= 100
    assert result["small"].size[1] <= 100
    assert result["medium"].size[0] <= 200
    assert result["medium"].size[1] <= 200
    assert result["large"].size[0] <= 400
    assert result["large"].size[1] <= 400
""")

print("thumbgen package generated successfully")
