#!/usr/bin/env python3
"""
Frameshift v2 — Smoke Test
Full pipeline, no mocks. Run before any deploy or scheduler change.
Usage: python3 tests/smoke.py [url]
Default URL: https://techcrunch.com/2026/06/09/its-not-faang-anymore-its-mangos/
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'watcher'))

from PIL import Image as _PILImage  # noqa: E402 — path must be set first

TEST_URL = (
    sys.argv[1] if len(sys.argv) > 1
    else "https://techcrunch.com/2026/06/09/its-not-faang-anymore-its-mangos/"
)

results = []


def check(name, fn):
    """Run fn(), record pass/fail, print result. Returns fn() result or None on failure."""
    start = time.time()
    try:
        result = fn()
        elapsed = time.time() - start
        print(f"  ✓ {name} ({elapsed:.1f}s)")
        results.append((name, True, None))
        return result
    except Exception as exc:
        elapsed = time.time() - start
        print(f"  ✗ {name} ({elapsed:.1f}s): {exc}")
        results.append((name, False, str(exc)))
        return None


print(f"\nFrameshift v2 — Smoke Test")
print(f"URL: {TEST_URL}")
print("─" * 50)

import writer  # noqa: E402

# ── 1. Scrape ────────────────────────────────────────────────────────────────
# Fetch the article and confirm the body extraction worked.
def _scrape():
    article = writer.scrape(TEST_URL)
    body_len = len(article.get("body", ""))
    if body_len <= 200:
        raise AssertionError(f"body too short: {body_len} chars")
    return article


article = check("scrape", _scrape)
if article is None:
    print("\n✗ FAILED — scrape failed, cannot continue")
    sys.exit(1)

# ── 2. Write (Groq) ──────────────────────────────────────────────────────────
# Full pipeline: scrape → Groq → validate → image fetch.
# generate() returns {"slides", "caption", "og_image_url", "image_obj"}.
# Note: this scrapes the URL a second time — intentional, tests the full generate() path.
data = check("write (Groq)", lambda: writer.generate(TEST_URL))
if data is None:
    print("\n✗ FAILED — write failed, cannot continue")
    sys.exit(1)

slides   = data["slides"]
caption  = data.get("caption", "")
image_obj = data.get("image_obj")          # PIL Image or None — already fetched by generate()

# ── 3. Caption ───────────────────────────────────────────────────────────────
def _check_caption():
    words = len(caption.split())
    if words < 50:
        raise AssertionError(f"caption only {words} words (minimum 50)")


check("caption (≥50 words)", _check_caption)

# ── 4. Slide structure ───────────────────────────────────────────────────────
def _check_structure():
    n = len(slides)
    if not (4 <= n <= 8):
        raise AssertionError(f"got {n} slides (expected 4–8 total)")
    if slides[0]["type"] != "cover":
        raise AssertionError(
            f"first slide is {slides[0]['type']!r}, expected 'cover'"
        )
    if slides[-1]["type"] != "cta":
        raise AssertionError(
            f"last slide is {slides[-1]['type']!r}, expected 'cta'"
        )
    n_middle = n - 2
    if not (2 <= n_middle <= 6):
        raise AssertionError(f"got {n_middle} middle slides (expected 2–6)")


check("slide structure (cover + 2–6 middle + cta)", _check_structure)

# ── 5. Image ─────────────────────────────────────────────────────────────────
# generate() already fetched the image; we validate the result without a second
# network call. None is not a failure — renderer uses a dark placeholder.
def _check_image():
    if image_obj is not None and not isinstance(image_obj, _PILImage.Image):
        raise AssertionError(
            f"image_obj is {type(image_obj).__name__}, expected PIL.Image.Image"
        )
    return image_obj


check("image (PIL Image or None)", _check_image)

# ── 6. Render + 7. Dimensions + 8. Delivery ─────────────────────────────────
# All three run inside the temp dir so PNGs exist for delivery.
from renderer import render_carousel  # noqa: E402
from delivery import send             # noqa: E402

with tempfile.TemporaryDirectory() as tmpdir:

    pngs = check("render", lambda: render_carousel(
        slides, image_obj=image_obj, output_dir=tmpdir, prefix="smoke"
    ))

    if pngs is None:
        print("\n✗ FAILED — render failed, cannot continue")
        sys.exit(1)

    def _check_count():
        if len(pngs) != len(slides):
            raise AssertionError(
                f"got {len(pngs)} PNGs for {len(slides)} slides"
            )

    check("PNG count matches slides", _check_count)

    def _check_dimensions():
        bad = []
        for path in pngs:
            size = _PILImage.open(path).size
            if size != (1080, 1350):
                bad.append(f"{os.path.basename(path)}: {size}")
        if bad:
            raise AssertionError("wrong dimensions — " + ", ".join(bad))

    check("slide dimensions (1080×1350)", _check_dimensions)

    # delivery.send() is synchronous — it calls asyncio.run() internally.
    check("telegram delivery", lambda: send(pngs, data=data, source_url=TEST_URL))

# ── Summary ──────────────────────────────────────────────────────────────────
print("─" * 50)
passed       = sum(1 for _, ok, _ in results if ok)
total        = len(results)
failed_list  = [(name, err) for name, ok, err in results if not ok]

if failed_list:
    print(f"\n✗ FAILED — {len(failed_list)}/{total} checks failed:")
    for name, err in failed_list:
        print(f"  ✗ {name}: {err}")
    sys.exit(1)
else:
    print(f"\n✓ ALL {total} CHECKS PASSED")
    sys.exit(0)
