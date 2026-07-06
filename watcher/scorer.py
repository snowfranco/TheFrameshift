"""
Frameshift v2 — watcher/scorer.py
Applies learned scoring weights to candidate list. Weights are updated by
feedback.py after each session based on operator approval/rejection signals.
"""

import json
import os
from urllib.parse import urlparse

_WEIGHTS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "store", "scoring_weights.json")
)

_DEFAULTS = {
    "source_weights": {},
    "topic_weights": {},
    "version": 1,
}


def load_weights() -> dict:
    try:
        with open(_WEIGHTS_PATH) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return dict(_DEFAULTS)
    except Exception as exc:
        print(f"[scorer] failed to load weights: {exc}")
        return dict(_DEFAULTS)


def save_weights(weights: dict) -> None:
    os.makedirs(os.path.dirname(_WEIGHTS_PATH), exist_ok=True)
    with open(_WEIGHTS_PATH, "w") as fh:
        json.dump(weights, fh, indent=2)


def adjust(item: dict, approved: bool) -> None:
    print(f"[scorer] Would adjust weights for: {item['source']} approved={approved}")


def score(item: dict) -> float:
    """
    Apply domain reliability to a candidate item's raw score.
    item must have 'score' (float) and 'url' (str).
    Returns adjusted score; falls back to raw score on any error.
    """
    raw = float(item.get("score", 0.0))
    try:
        host = urlparse(item.get("url", "")).netloc
        domain = host[4:] if host.startswith("www.") else host
    except Exception:
        return raw

    weights = load_weights()
    rec = weights.get("domain_reliability", {}).get(domain)
    if rec and rec.get("attempts", 0) >= 3:
        raw *= rec.get("reliability", 1.0)
    return raw
