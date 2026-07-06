"""
Frameshift v2 — watcher/feedback.py
Tracks scrape reliability per domain. Logs all attempts to
store/feedback_log.json and updates domain_reliability in
store/scoring_weights.json for scorer.py to consume.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

_WATCHER_DIR  = os.path.dirname(os.path.abspath(__file__))
_STORE_DIR    = os.path.normpath(os.path.join(_WATCHER_DIR, "..", "store"))
_FEEDBACK_LOG = os.path.join(_STORE_DIR, "feedback_log.json")
_WEIGHTS_PATH = os.path.normpath(os.path.join(_WATCHER_DIR, "..", "store", "scoring_weights.json"))

_WARN_THRESHOLD = 0.3
_MIN_ATTEMPTS   = 3


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return url


def record_scrape_attempt(url: str, success: bool, reason: str | None = None) -> None:
    domain = _domain(url)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "scrape_attempt",
        "domain": domain,
        "url": url,
        "success": success,
        "reason": reason,
    }
    os.makedirs(_STORE_DIR, exist_ok=True)
    try:
        with open(_FEEDBACK_LOG) as fh:
            log_data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        log_data = []
    log_data.append(entry)
    with open(_FEEDBACK_LOG, "w") as fh:
        json.dump(log_data, fh, indent=2)
    adjust_domain_reliability(domain, success)


def adjust_domain_reliability(domain: str, success: bool) -> None:
    try:
        with open(_WEIGHTS_PATH) as fh:
            weights = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        weights = {"source_weights": {}, "topic_weights": {}, "version": 1}

    rel = weights.setdefault("domain_reliability", {})
    rec = rel.setdefault(domain, {"attempts": 0, "failures": 0, "reliability": 1.0})

    rec["attempts"] += 1
    if not success:
        rec["failures"] += 1
    rec["reliability"] = (rec["attempts"] - rec["failures"]) / rec["attempts"]

    if rec["attempts"] >= _MIN_ATTEMPTS and rec["reliability"] < _WARN_THRESHOLD:
        print(
            f"[feedback] {domain} reliability {rec['reliability']:.0%} — "
            "consider adding to blocklist",
            file=sys.stderr,
        )

    os.makedirs(os.path.dirname(_WEIGHTS_PATH), exist_ok=True)
    with open(_WEIGHTS_PATH, "w") as fh:
        json.dump(weights, fh, indent=2)
