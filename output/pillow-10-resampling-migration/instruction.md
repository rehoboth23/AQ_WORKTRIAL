Hey, I need help fixing the thumbgen library at /app/thumbgen. We recently upgraded its Pillow dependency to 10.x, and now the entire test suite is broken. The library source code is in /app/thumbgen/thumbgen/ — please fix the source files there so all tests pass.

Do NOT modify any test files or pyproject.toml.

Run `pytest -v` from /app/thumbgen to check your progress.

Verification will confirm:
1. Pillow version remains >= 10.0
2. No removed Pillow attributes (like Image.ANTIALIAS) appear in the source files
3. All four public functions work correctly: resize_exact, resize_proportional, apply_text_watermark, and optimize_for_web
4. The project's own test suite passes completely
