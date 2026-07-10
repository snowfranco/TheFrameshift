"""
Unit tests for the approval state machine helpers in watcher/bot.py.
No network, no Telegram — pure function tests plus pending-file lifecycle.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "watcher"))

import bot  # noqa: E402


# ── _parse_approval ───────────────────────────────────────────────────────────

def test_parse_all():
    assert bot._parse_approval("ALL", 5) == [1, 2, 3, 4, 5]
    assert bot._parse_approval("all", 3) == [1, 2, 3]


def test_parse_skip():
    assert bot._parse_approval("SKIP", 5) == "SKIP"
    assert bot._parse_approval("skip", 5) == "SKIP"


def test_parse_indices():
    assert bot._parse_approval("1,3", 5) == [1, 3]
    assert bot._parse_approval("1 3 5", 5) == [1, 3, 5]
    assert bot._parse_approval("1, 3, 5", 5) == [1, 3, 5]


def test_parse_out_of_range_dropped():
    assert bot._parse_approval("1,9", 5) == [1]
    assert bot._parse_approval("9", 5) is None  # nothing valid left


def test_parse_non_approval_text():
    assert bot._parse_approval("thanks, looks good", 5) is None
    assert bot._parse_approval("go for 1 and 3", 5) is None


# ── _looks_like_approval ──────────────────────────────────────────────────────

def test_looks_like_approval_positive():
    assert bot._looks_like_approval("ALL")
    assert bot._looks_like_approval("skip")
    assert bot._looks_like_approval("1,3")
    assert bot._looks_like_approval("2")


def test_looks_like_approval_negative():
    assert not bot._looks_like_approval("nice list")
    assert not bot._looks_like_approval("go 1 3")
    assert not bot._looks_like_approval("")


# ── pending-file lifecycle ────────────────────────────────────────────────────

def test_pending_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "_STORE_DIR", str(tmp_path))
    monkeypatch.setattr(bot, "_PENDING_PATH", str(tmp_path / "pending_candidates.json"))

    candidates = [{"title": "A", "url": "https://a.example"}]
    bot._save_pending(candidates)
    loaded = bot._load_pending()
    assert loaded["candidates"] == candidates
    assert not bot._pending_expired(loaded)

    bot._clear_pending()
    assert bot._load_pending() is None
    bot._clear_pending()  # idempotent — no raise on missing file


def test_pending_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "_PENDING_PATH", str(tmp_path / "pending_candidates.json"))
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    with open(bot._PENDING_PATH, "w") as fh:
        json.dump({"timestamp": stale_ts, "candidates": []}, fh)
    assert bot._pending_expired(bot._load_pending())


def test_pending_malformed_timestamp_treated_expired():
    assert bot._pending_expired({"timestamp": "not-a-date", "candidates": []})
    assert bot._pending_expired({"candidates": []})


def test_load_pending_corrupt_json(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "_PENDING_PATH", str(tmp_path / "pending_candidates.json"))
    with open(bot._PENDING_PATH, "w") as fh:
        fh.write("{ not json")
    assert bot._load_pending() is None


# ── PID lock ─────────────────────────────────────────────────────────────────

def test_pid_lock_acquire_and_release(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "_STORE_DIR", str(tmp_path))
    monkeypatch.setattr(bot, "_PID_PATH", str(tmp_path / "bot.pid"))

    bot._acquire_pid_lock()
    with open(bot._PID_PATH) as fh:
        assert fh.read().strip() == str(os.getpid())

    bot._release_pid_lock()
    assert not os.path.exists(bot._PID_PATH)


def test_pid_lock_stale_taken_over(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "_STORE_DIR", str(tmp_path))
    monkeypatch.setattr(bot, "_PID_PATH", str(tmp_path / "bot.pid"))

    with open(bot._PID_PATH, "w") as fh:
        fh.write("999999999")  # PID that cannot exist

    bot._acquire_pid_lock()  # must not exit
    with open(bot._PID_PATH) as fh:
        assert fh.read().strip() == str(os.getpid())
    bot._release_pid_lock()


def test_pid_lock_live_process_refused(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(bot, "_STORE_DIR", str(tmp_path))
    monkeypatch.setattr(bot, "_PID_PATH", str(tmp_path / "bot.pid"))

    with open(bot._PID_PATH, "w") as fh:
        fh.write("1")  # PID 1 is always alive

    # root sees "already running"; unprivileged sees "appears to be running"
    with pytest.raises(SystemExit, match="running"):
        bot._acquire_pid_lock()


def test_release_only_own_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "_PID_PATH", str(tmp_path / "bot.pid"))
    with open(bot._PID_PATH, "w") as fh:
        fh.write("424242")
    bot._release_pid_lock()  # not ours — must NOT delete
    assert os.path.exists(bot._PID_PATH)
