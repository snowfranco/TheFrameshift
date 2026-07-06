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

_VALID_SLIDES = [
    {"type": "cover", "headline": "Test headline here", "category": "AI & XR", "image_query": "test image query"},
    {"type": "stat",  "eyebrow": "Signal", "number": "73%", "unit": "adoption rate", "context": "Up from 40% last year."},
    {"type": "quote", "text": "This changes everything.", "attribution": "Someone, CEO — Co"},
    {"type": "cta",   "headline": "Follow The Frameshift for daily dispatches."},
]


def _mock_groq(slides):
    """Return a mock requests.Response that looks like a Groq success reply."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps({"slides": slides})}}]
    }
    return resp


def _run_write(slides):
    with patch.dict(os.environ, {"GROQ_API_KEY": "fake-key"}), \
         patch("writer.requests.post", return_value=_mock_groq(slides)):
        return writer.write(_ARTICLE)


# ── Valid input ───────────────────────────────────────────────────────────────

def test_valid_slides_accepted():
    result = _run_write(_VALID_SLIDES)
    assert len(result) == 4
    assert result[0]["type"] == "cover"
    assert result[-1]["type"] == "cta"


# ── First / last slide constraints ───────────────────────────────────────────

def test_first_slide_not_cover_rejected():
    bad = [_VALID_SLIDES[1], _VALID_SLIDES[1], _VALID_SLIDES[2], _VALID_SLIDES[3]]
    with pytest.raises(ValueError, match="first slide must be"):
        _run_write(bad)


def test_last_slide_not_cta_rejected():
    bad = [_VALID_SLIDES[0], _VALID_SLIDES[1], _VALID_SLIDES[2], _VALID_SLIDES[1]]
    with pytest.raises(ValueError, match="last slide must be"):
        _run_write(bad)


# ── Middle-slide count constraints ───────────────────────────────────────────

def test_too_few_middle_slides_rejected():
    # only 1 middle slide
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
