"""
Unit tests for watcher/renderer.py.
Checks: each slide type renders to (1080×1350), background spot colors,
and render_carousel writes real PNG files to disk.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "watcher"))

from renderer import (  # noqa: E402
    BLACK, H, OFF_WHITE, W,
    TEST_CAROUSEL,
    render_carousel,
    render_context, render_contrast, render_cover, render_cta,
    render_explainer, render_quote, render_signal, render_stat, render_timeline,
)

# ── Fixtures — pulled from renderer's own TEST_CAROUSEL + one minimal explainer ──

_COVER     = TEST_CAROUSEL[0]
_STAT      = TEST_CAROUSEL[1]
_QUOTE     = TEST_CAROUSEL[2]
_CONTEXT   = TEST_CAROUSEL[3]
_CONTRAST  = TEST_CAROUSEL[4]
_TIMELINE  = TEST_CAROUSEL[5]
_SIGNAL    = TEST_CAROUSEL[6]
_CTA       = TEST_CAROUSEL[7]
_EXPLAINER = {
    "type": "explainer",
    "kicker": "In short",
    "question": "What is spatial computing?",
    "answer": "It means computers that understand and interact with 3D physical space.",
}

# ── Size tests — every slide type must produce a 1080×1350 image ──────────────

@pytest.mark.parametrize("render_fn,slide", [
    (render_cover,     _COVER),
    (render_stat,      _STAT),
    (render_quote,     _QUOTE),
    (render_context,   _CONTEXT),
    (render_contrast,  _CONTRAST),
    (render_timeline,  _TIMELINE),
    (render_explainer, _EXPLAINER),
    (render_signal,    _SIGNAL),
    (render_cta,       _CTA),
])
def test_render_size(render_fn, slide):
    img = render_fn(slide)
    assert img.size == (W, H), f"{render_fn.__name__} produced {img.size}, expected ({W}, {H})"


# ── Spot color: CTA background is pure black ──────────────────────────────────

def test_cta_background_is_black():
    img = render_cta(_CTA)
    assert img.getpixel((10, 10)) == BLACK


# ── Spot color: all content slides use OFF_WHITE background ───────────────────
# Pixel (10, 10) is above the header zone (header starts at y=60), guaranteed bg.

@pytest.mark.parametrize("render_fn,slide", [
    (render_stat,      _STAT),
    (render_quote,     _QUOTE),
    (render_context,   _CONTEXT),
    (render_contrast,  _CONTRAST),
    (render_timeline,  _TIMELINE),
    (render_explainer, _EXPLAINER),
    (render_signal,    _SIGNAL),
])
def test_content_background_is_off_white(render_fn, slide):
    img = render_fn(slide)
    assert img.getpixel((10, 10)) == OFF_WHITE, (
        f"{render_fn.__name__}: pixel (10,10) is {img.getpixel((10,10))}, expected OFF_WHITE {OFF_WHITE}"
    )


# ── render_carousel — files on disk, right count, non-zero size ───────────────

def test_render_carousel_produces_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = render_carousel(TEST_CAROUSEL, output_dir=tmpdir, prefix="test")
        assert len(paths) == len(TEST_CAROUSEL)
        for p in paths:
            assert os.path.exists(p), f"missing file: {p}"
            assert os.path.getsize(p) > 0, f"empty file: {p}"
