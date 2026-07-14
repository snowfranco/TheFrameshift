"""
Unit tests for the slide-schema validator in watcher/writer.py.
Mocks the Groq HTTP call so no API key or network is needed.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "watcher"))

import writer  # noqa: E402

# ── Helpers ───────────────────────────────────────────────────────────────────

_ARTICLE = {"title": "Test", "body": "x" * 500, "og_image_url": None}

_CAPTION = (
    "A major AR acquisition closed this week, marking the third such deal this "
    "quarter. The buyer gains waveguide patents and a 40-person optics team. "
    "Analysts read it as consolidation ahead of the next hardware cycle."
)

_VALID_SLIDES = [
    {"type": "cover", "headline": "Test headline here", "category": "AI & XR", "image_query": "test image query"},
    {"type": "stat",  "eyebrow": "Signal", "number": "73%", "unit": "adoption rate", "context": "Up from 40% last year."},
    {"type": "quote", "text": "This changes everything.", "attribution": "Someone, CEO — Co"},
    {"type": "cta",   "headline": "We track every AR acquisition before it goes mainstream."},
]


def _mock_groq(slides, caption=_CAPTION):
    """Return a mock requests.Response that looks like a Groq success reply."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps({"slides": slides, "caption": caption})}}]
    }
    return resp


def _run_write(slides, caption=_CAPTION):
    with patch.dict(os.environ, {"GROQ_API_KEY": "fake-key"}), \
         patch("writer.requests.post", return_value=_mock_groq(slides, caption)):
        return writer.write(_ARTICLE)


# ── Valid input ───────────────────────────────────────────────────────────────

def test_valid_slides_accepted():
    result = _run_write(_VALID_SLIDES)
    assert result["caption"] == _CAPTION
    slides = result["slides"]
    assert len(slides) == 4
    assert slides[0]["type"] == "cover"
    assert slides[-1]["type"] == "cta"
    assert slides[-1]["headline"] == "We track every AR acquisition before it goes mainstream."


# ── CTA handling ─────────────────────────────────────────────────────────────

def test_missing_cta_appends_default():
    no_cta = _VALID_SLIDES[:3]  # cover + 2 middle, no cta
    result = _run_write(no_cta)
    slides = result["slides"]
    assert slides[-1]["type"] == "cta"
    assert len(slides[-1]["headline"]) > 10  # default follow hook, not empty


def test_stray_mid_list_cta_dropped():
    stray = [
        _VALID_SLIDES[0],
        _VALID_SLIDES[3],  # cta in the middle — model noise
        _VALID_SLIDES[1],
        _VALID_SLIDES[2],
        _VALID_SLIDES[3],
    ]
    result = _run_write(stray)
    slides = result["slides"]
    assert [s["type"] for s in slides].count("cta") == 1
    assert slides[-1]["type"] == "cta"


# ── First slide constraint ───────────────────────────────────────────────────

def test_first_slide_not_cover_rejected():
    bad = [_VALID_SLIDES[1], _VALID_SLIDES[1], _VALID_SLIDES[2], _VALID_SLIDES[3]]
    with pytest.raises(ValueError, match="first slide must be"):
        _run_write(bad)


# ── Middle-slide count constraints ───────────────────────────────────────────

def test_too_few_middle_slides_rejected():
    # only 1 middle slide between cover and cta
    bad = [_VALID_SLIDES[0], _VALID_SLIDES[1], _VALID_SLIDES[3]]
    with pytest.raises(ValueError, match="2.6 middle slides"):
        _run_write(bad)


def test_too_many_middle_slides_rejected():
    middle = [_VALID_SLIDES[1]] * 7
    bad = [_VALID_SLIDES[0]] + middle + [_VALID_SLIDES[3]]
    with pytest.raises(ValueError, match="2.6 middle slides"):
        _run_write(bad)


# ── Unknown slide type ────────────────────────────────────────────────────────

def test_unknown_slide_type_rejected():
    bad = [
        _VALID_SLIDES[0],
        {"type": "flashcard", "headline": "Unknown type"},
        _VALID_SLIDES[2],
        _VALID_SLIDES[3],
    ]
    with pytest.raises(ValueError, match="unknown slide type"):
        _run_write(bad)


# ── Caption constraints ───────────────────────────────────────────────────────

def test_short_caption_rejected():
    with pytest.raises(ValueError, match="caption must be at least 80"):
        _run_write(_VALID_SLIDES, caption="Too short.")


def test_missing_caption_rejected():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps({"slides": _VALID_SLIDES})}}]
    }
    with patch.dict(os.environ, {"GROQ_API_KEY": "fake-key"}), \
         patch("writer.requests.post", return_value=resp):
        with pytest.raises(ValueError, match="caption must be at least 80"):
            writer.write(_ARTICLE)


# ── Missing slides key ────────────────────────────────────────────────────────

def test_missing_slides_key_rejected():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": '{"not_slides": []}'}}]
    }
    with patch.dict(os.environ, {"GROQ_API_KEY": "fake-key"}), \
         patch("writer.requests.post", return_value=resp):
        with pytest.raises(ValueError, match="'slides' key missing or empty"):
            writer.write(_ARTICLE)


# ── Quality warnings (soft — must not raise) ─────────────────────────────────

def test_thin_signal_implication_warns_but_passes(capsys):
    slides = [
        _VALID_SLIDES[0],
        {"type": "signal", "kicker": "What this means", "headline": "Big shift ahead",
         "implication": "This could revolutionize everything.", "tag": "AI"},
        _VALID_SLIDES[2],
        _VALID_SLIDES[3],
    ]
    result = _run_write(slides)
    assert result["slides"][-1]["type"] == "cta"
    err = capsys.readouterr().err
    assert "QUALITY WARNING" in err
    assert "implication" in err


def test_thin_context_body_warns_but_passes(capsys):
    slides = [
        _VALID_SLIDES[0],
        {"type": "context", "kicker": "What happened", "headline": "A deal closed",
         "body": "One short sentence only.", "use_image": False},
        _VALID_SLIDES[2],
        _VALID_SLIDES[3],
    ]
    result = _run_write(slides)
    assert result["slides"][-1]["type"] == "cta"
    err = capsys.readouterr().err
    assert "QUALITY WARNING" in err
    assert "context.body" in err
