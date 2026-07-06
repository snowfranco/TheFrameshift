import os
import glob
import tempfile
import sys

import pytest
from PIL import Image, ImageChops

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'watcher'))
from renderer import render_carousel, TEST_CAROUSEL

BASELINE_DIR = os.path.join(os.path.dirname(__file__), 'baselines')

# TEST_CAROUSEL covers 8 of 9 slide types — explainer is absent.
# Insert it between timeline (index 5) and signal (index 6) so the
# full palette is exercised in both baseline generation and live tests.
_EXPLAINER_SLIDE = {
    "type": "explainer",
    "kicker": "Worth knowing",
    "question": "Why does AR need a killer app to win the mass market?",
    "answer": (
        "Every display category found its mass market through a dominant use case. "
        "4K through streaming, high-refresh through gaming. "
        "Without a killer app, AR stays a solution looking for a problem."
    ),
}

REGRESSION_CAROUSEL = TEST_CAROUSEL[:6] + [_EXPLAINER_SLIDE] + TEST_CAROUSEL[6:]

SLIDE_TYPES = [
    "cover", "stat", "quote", "context",
    "contrast", "timeline", "explainer", "signal", "cta",
]


def get_baseline(slide_type):
    matches = glob.glob(os.path.join(BASELINE_DIR, f"baseline_*_{slide_type}.png"))
    assert matches, f"No baseline found for slide type: {slide_type}"
    return matches[0]


def _render_fresh():
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = render_carousel(REGRESSION_CAROUSEL, output_dir=tmpdir, prefix="test")
        return {
            os.path.basename(p).split("_", 2)[2].replace(".png", ""): Image.open(p).copy()
            for p in paths
        }


@pytest.fixture(scope="module")
def fresh_slides():
    return _render_fresh()


@pytest.mark.parametrize("slide_type", SLIDE_TYPES)
def test_slide_dimensions(fresh_slides, slide_type):
    """Every slide must be exactly 1080x1350px."""
    img = fresh_slides[slide_type]
    assert img.size == (1080, 1350), (
        f"{slide_type}: expected (1080, 1350), got {img.size}"
    )


@pytest.mark.parametrize("slide_type", SLIDE_TYPES)
def test_slide_pixel_diff(fresh_slides, slide_type):
    """Rendered slide must exactly match approved baseline."""
    baseline = Image.open(get_baseline(slide_type))
    rendered = fresh_slides[slide_type]
    diff = ImageChops.difference(baseline, rendered)
    bbox = diff.getbbox()
    assert bbox is None, (
        f"{slide_type}: pixel diff detected at {bbox}. "
        "Run 'make update-baselines' if this change is intentional."
    )
