"""
Frameshift v2 — watcher/bot.py
Main entry point: Telegram bot + APScheduler daily flow.

On-demand:  /carousel <url>  → generate + deliver carousel
Manual:     /run             → trigger ingestion + candidate list
Approval:   ALL / 1,3,5 / SKIP → batch generate approved stories
Daily:      8:00 AM Toronto  → ingestion + approval wait + batch delivery

Usage:
    python3 watcher/bot.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import requests
import sys
from datetime import datetime, time as dt_time, timedelta, timezone
from urllib.parse import urlparse

# watcher imports work from any invocation path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

_ENV_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
)
load_dotenv(_ENV_PATH)

import feedback as _feedback        # noqa: E402
import ingestion as _ingestion      # noqa: E402
import delivery as _delivery        # noqa: E402
import writer as _writer            # noqa: E402
from renderer import render_carousel as _render_carousel  # noqa: E402

from telegram import Update                              # noqa: E402
from telegram.ext import (                              # noqa: E402
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── Config ────────────────────────────────────────────────────────────────────

_WATCHER_DIR   = os.path.dirname(os.path.abspath(__file__))
_STORE_DIR     = os.path.normpath(os.path.join(_WATCHER_DIR, "..", "store"))
_PENDING_PATH  = os.path.join(_STORE_DIR, "pending_candidates.json")
_RUN_LOG_PATH  = os.path.join(_STORE_DIR, "run_log.json")

_APPROVAL_TIMEOUT_HOURS = 2
_DAILY_HOUR   = 8
_DAILY_MINUTE = 0
_TIMEZONE     = "America/Toronto"
_WRITING_AGENT_INBOX = os.path.expanduser("~/writing_agent/inbox")
_URL_RE = re.compile(r"https?://\S+")

logging.basicConfig(
    format="%(asctime)s %(levelname)s [bot] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")


# ── Pending state ─────────────────────────────────────────────────────────────

def _save_pending(candidates: list) -> None:
    os.makedirs(_STORE_DIR, exist_ok=True)
    with open(_PENDING_PATH, "w") as fh:
        json.dump(
            {"timestamp": datetime.now(timezone.utc).isoformat(), "candidates": candidates},
            fh, indent=2,
        )


def _load_pending() -> dict | None:
    try:
        with open(_PENDING_PATH) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _clear_pending() -> None:
    try:
        os.remove(_PENDING_PATH)
    except FileNotFoundError:
        pass


def _pending_expired(payload: dict) -> bool:
    try:
        ts = datetime.fromisoformat(payload["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts) > timedelta(hours=_APPROVAL_TIMEOUT_HOURS)
    except Exception:
        return True


# ── Run log ───────────────────────────────────────────────────────────────────

def _log_run(entry: dict) -> None:
    os.makedirs(_STORE_DIR, exist_ok=True)
    try:
        with open(_RUN_LOG_PATH) as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    data.append(entry)
    with open(_RUN_LOG_PATH, "w") as fh:
        json.dump(data, fh, indent=2)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def _parse_approval(text: str, total: int) -> list[int] | str | None:
    """
    Returns list of 1-based story indices, "SKIP", or None (not an approval).
    Recognises: ALL | SKIP | 1,3,5 | 1 3 5 | 1, 3, 5
    """
    t = text.strip().upper()
    if t == "ALL":
        return list(range(1, total + 1))
    if t == "SKIP":
        return "SKIP"
    if re.fullmatch(r"[\d\s,]+", t):
        indices = [int(n) for n in re.findall(r"\d+", t) if 1 <= int(n) <= total]
        return indices or None
    return None


def _owner_chat(update: Update) -> bool:
    """True if the message comes from the configured owner chat."""
    owner = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return not owner or str(update.message.chat_id) == owner


# ── Core: generate + deliver one story ───────────────────────────────────────

_SCRAPE_SIGNALS = ("Request failed", "Jina fallback also failed", "Body too short", "paywalled")

_FETCH_FAIL_MSG = (
    "⚠️ Couldn't fetch that article.\n"
    "The site may be paywalled, bot-blocked, or JavaScript-rendered.\n"
    "Try a different URL or a cached version (archive.ph, 12ft.io)."
)


def _is_scrape_error(msg: str) -> bool:
    return any(sig in msg for sig in _SCRAPE_SIGNALS)


def _strip_raw_json(msg: str) -> str:
    """Remove the '\\n\\nRaw: ...' tail appended by write() validation errors."""
    return msg.split("\n\nRaw:")[0].strip()


def _serper_alternative(headline: str) -> str | None:
    """Search Serper for alternative coverage of headline. Returns first result URL or None."""
    api_key = os.environ.get("SERPER_API_KEY", "").strip()
    if not api_key:
        return None
    query = (
        f"{headline} site:techcrunch.com OR site:theverge.com "
        "OR site:wired.com OR site:arstechnica.com"
    )
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": 1},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("organic", [])
        return results[0]["link"] if results else None
    except Exception:
        return None


async def _carousel_for(
    url: str,
    title: str,
    index: int,
    total: int,
    reply,
) -> None:
    print(f"[bot] generating carousel {index}/{total}...")
    entry: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "slides_count": 0,
        "delivered": False,
        "error": None,
    }
    try:
        data = await asyncio.to_thread(_writer.generate, url)
        image_obj = data.get("image_obj")
        logo_obj = data.get("logo_obj")
        png_paths = await asyncio.to_thread(
            lambda: _render_carousel(data["slides"], image_obj=image_obj, logo_obj=logo_obj, stat_image_obj=data.get("stat_image_obj"))
        )
        await asyncio.to_thread(_delivery.send, png_paths, data, url)
        entry["slides_count"] = len(data["slides"])
        entry["delivered"] = True
        _feedback.record_scrape_attempt(url, True)
    except Exception as exc:
        msg = str(exc)
        entry["error"] = msg
        log.error("carousel error %r: %s", url, exc)
        if _is_scrape_error(msg):
            _feedback.record_scrape_attempt(url, False, reason=msg)
            alt_url = _serper_alternative(title)
            if alt_url:
                log.info("story %d failed on %s, trying alternative: %s", index, url, alt_url)
                print(f"[bot] story {index} failed on {url}, trying alternative: {alt_url}", file=sys.stderr)
                try:
                    data = await asyncio.to_thread(_writer.generate, alt_url)
                    image_obj = data.get("image_obj")
                    logo_obj = data.get("logo_obj")
                    png_paths = await asyncio.to_thread(
                        lambda: _render_carousel(data["slides"], image_obj=image_obj, logo_obj=logo_obj, stat_image_obj=data.get("stat_image_obj"))
                    )
                    await asyncio.to_thread(_delivery.send, png_paths, data, alt_url)
                    entry["slides_count"] = len(data["slides"])
                    entry["delivered"] = True
                    entry["error"] = None
                    entry["url"] = alt_url
                    _feedback.record_scrape_attempt(alt_url, True)
                except Exception as alt_exc:
                    entry["error"] = str(alt_exc)
                    log.error("alternative also failed for %r: %s", alt_url, alt_exc)
                    if reply:
                        await reply(_FETCH_FAIL_MSG)
            elif reply:
                await reply(_FETCH_FAIL_MSG)
        elif reply:
            await reply(f"[bot] story {index}/{total} failed: {_strip_raw_json(msg)}")
    _log_run(entry)


# ── Shared ingestion trigger ──────────────────────────────────────────────────

async def _trigger_ingestion() -> list:
    candidates = await asyncio.to_thread(_ingestion.run)
    _save_pending(candidates)
    return candidates


# ── Handlers ─────────────────────────────────────────────────────────────────

async def cmd_carousel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /carousel <url>")
        return

    url = args[0].strip()
    if not _valid_url(url):
        await update.message.reply_text(f"Invalid URL: {url!r}")
        return

    await update.message.reply_text("Generating carousel...")

    entry: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "slides_count": 0,
        "delivered": False,
        "error": None,
    }
    try:
        data = await asyncio.to_thread(_writer.generate, url)
        image_obj = data.get("image_obj")
        logo_obj = data.get("logo_obj")
        png_paths = await asyncio.to_thread(
            lambda: _render_carousel(data["slides"], image_obj=image_obj, logo_obj=logo_obj, stat_image_obj=data.get("stat_image_obj"))
        )
        await asyncio.to_thread(_delivery.send, png_paths, data, url)
        entry["slides_count"] = len(data["slides"])
        entry["delivered"] = True
        _feedback.record_scrape_attempt(url, True)
    except ValueError as exc:
        msg = str(exc)
        entry["error"] = msg
        if _is_scrape_error(msg):
            _feedback.record_scrape_attempt(url, False, reason=msg)
            await update.message.reply_text(_FETCH_FAIL_MSG)
        else:
            # Generation error — retry once
            await update.message.reply_text("Generation hiccup — retrying...")
            try:
                data = await asyncio.to_thread(_writer.generate, url)
                image_obj = data.get("image_obj")
                logo_obj = data.get("logo_obj")
                png_paths = await asyncio.to_thread(
                    lambda: _render_carousel(data["slides"], image_obj=image_obj, logo_obj=logo_obj, stat_image_obj=data.get("stat_image_obj"))
                )
                await asyncio.to_thread(_delivery.send, png_paths, data, url)
                entry["slides_count"] = len(data["slides"])
                entry["delivered"] = True
                entry["error"] = None
                _feedback.record_scrape_attempt(url, True)
            except Exception as exc2:
                msg2 = str(exc2)
                entry["error"] = msg2
                log.error("generation failed for %r: %s", url, exc2)
                await update.message.reply_text(f"Generation failed: {_strip_raw_json(msg2)}")
    except Exception as exc:
        entry["error"] = str(exc)
        await update.message.reply_text(f"Error: {exc}")
    _log_run(entry)


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_chat(update):
        return
    await update.message.reply_text("[bot] running ingestion...")
    try:
        candidates = await _trigger_ingestion()
        await update.message.reply_text(
            f"[bot] {len(candidates)} candidates sent. "
            "Reply ALL, story numbers (e.g. 1,3), or SKIP."
        )
    except Exception as exc:
        log.error("ingestion error: %s", exc)
        await update.message.reply_text(f"[bot] ingestion error: {exc}")


async def cmd_substack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /substack <prompt> — queue a writing_agent article generation."""
    if not _owner_chat(update):
        return

    text = update.message.text or ""
    replied_text: str | None = None
    if update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text or ""

    body = re.sub(r"^/substack\s*", "", text.strip(), flags=re.IGNORECASE)

    urls = _URL_RE.findall(body)
    if replied_text:
        urls += _URL_RE.findall(replied_text)
    seen: set = set()
    unique_urls = [u for u in urls if not (u in seen or seen.add(u))]  # type: ignore[func-returns-value]

    prompt = _URL_RE.sub("", body).strip()
    prompt = re.sub(r"\s{2,}", " ", prompt).strip()

    if not prompt:
        await update.message.reply_text(
            "Usage: /substack <prompt text>\n"
            "Include URLs in the message or reply to a message containing them."
        )
        return

    ts = datetime.now(timezone.utc)
    date_str = ts.strftime("%Y-%m-%d")
    words = re.sub(r"[^a-z0-9\s]", "", prompt.lower()).split()
    slug = f"{date_str}_" + ("-".join(words[:4]) if words else "untitled")

    payload = {
        "voice":            "snow_frameshift_substack",
        "format":           "substack_article",
        "reference_urls":   unique_urls,
        "editorial_prompt": prompt,
        "target_length":    1200,
        "slug":             slug,
        "received_at":      ts.isoformat(),
    }

    os.makedirs(_WRITING_AGENT_INBOX, exist_ok=True)
    inbox_path = os.path.join(_WRITING_AGENT_INBOX, f"{slug}.json")
    with open(inbox_path, "w") as f:
        json.dump(payload, f, indent=2)

    log.info("substack queued: %s (%d URL(s))", slug, len(unique_urls))
    await update.message.reply_text(
        f"Queued. Slug: {slug}\nURLs: {len(unique_urls)}\nI'll notify you when ready."
    )


async def msg_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_chat(update):
        return

    text = (update.message.text or "").strip()
    pending = _load_pending()
    if not pending:
        return

    if _pending_expired(pending):
        _clear_pending()
        log.info("approval window expired — cleared pending")
        return

    candidates = pending.get("candidates", [])
    result = _parse_approval(text, len(candidates))
    if result is None:
        return  # not a recognised approval pattern

    _clear_pending()

    if result == "SKIP":
        await update.message.reply_text("[bot] run skipped.")
        return

    approved = [candidates[i - 1] for i in result]
    if not approved:
        await update.message.reply_text("[bot] no valid story numbers selected.")
        return

    await update.message.reply_text(f"[bot] approved {len(approved)} story/stories — generating...")
    for idx, story in enumerate(approved, 1):
        await _carousel_for(
            story["url"], story["title"], idx, len(approved), update.message.reply_text
        )
    await update.message.reply_text(f"[bot] batch complete — {len(approved)} carousel(s) delivered.")


# ── Daily scheduled job ───────────────────────────────────────────────────────

async def daily_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    log.info("daily job triggered")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    try:
        candidates = await _trigger_ingestion()
        if chat_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"[bot] {len(candidates)} candidates above. "
                    "Reply ALL, story numbers (e.g. 1,3), or SKIP (2h window)."
                ),
            )
    except Exception as exc:
        log.error("daily job error: %s", exc)
        if chat_id:
            try:
                await context.bot.send_message(
                    chat_id=chat_id, text=f"[bot] daily job error: {exc}"
                )
            except Exception:
                pass


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        sys.exit("[bot] TELEGRAM_BOT_TOKEN not set — check .env")

    import pytz
    toronto_tz = pytz.timezone(_TIMEZONE)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("carousel", cmd_carousel))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("substack", cmd_substack))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_approval))

    run_time = dt_time(_DAILY_HOUR, _DAILY_MINUTE, tzinfo=toronto_tz)
    # misfire_grace_time=3600: fire the job even if the event loop was busy at the exact second
    job = app.job_queue.run_daily(daily_job, time=run_time, name="daily_ingestion",
                                  job_kwargs={"misfire_grace_time": 3600})

    try:
        next_run = job.next_t
    except Exception:
        next_run = "unknown"

    print(f"[bot] starting — on-demand: /carousel <url> | daily: 8:00 AM Toronto")
    print(f"[bot] scheduler armed — next run: {next_run}")
    print("[bot] polling... (Ctrl+C to stop)")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
