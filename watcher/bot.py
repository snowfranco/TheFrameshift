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
import atexit
import functools
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
_PID_PATH      = os.path.join(_STORE_DIR, "bot.pid")

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


def _looks_like_approval(text: str) -> bool:
    """True if text matches an approval shape (ALL / SKIP / digits) at all,
    regardless of whether a pending list exists. Used to decide whether a
    plain message deserves an approval-flow response or is just chat."""
    t = text.strip().upper()
    return t in ("ALL", "SKIP") or bool(re.fullmatch(r"[\d\s,]+", t))


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
    if not owner:
        return True
    incoming = str(update.message.chat_id)
    if incoming != owner:
        # The single most common cause of "/run silently does nothing":
        # the message arrived from a chat that doesn't match TELEGRAM_CHAT_ID.
        log.warning(
            "message from chat %s ignored — TELEGRAM_CHAT_ID is %s "
            "(fix .env if this is you)",
            incoming, owner,
        )
        return False
    return True


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
) -> bool:
    """Generate + deliver one story. Returns True if delivered.
    Every failure path replies to Telegram — never silent."""
    log.info("generating carousel %d/%d... (%s)", index, total, url)
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
        log.info("carousel %d/%d delivered", index, total)
        _feedback.record_scrape_attempt(url, True)
    except Exception as exc:
        msg = str(exc)
        entry["error"] = msg
        log.error("carousel error %r: %s", url, exc)
        if _is_scrape_error(msg):
            _feedback.record_scrape_attempt(url, False, reason=msg)
            # requests-based Serper call — keep it off the event loop
            alt_url = await asyncio.to_thread(_serper_alternative, title)
            if alt_url:
                log.info("story %d failed on %s, trying alternative: %s", index, url, alt_url)
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
                    log.info("carousel %d/%d delivered (via alternative source)", index, total)
                    _feedback.record_scrape_attempt(alt_url, True)
                except Exception as alt_exc:
                    entry["error"] = str(alt_exc)
                    log.error("alternative also failed for %r: %s", alt_url, alt_exc)
                    if reply:
                        await reply(f"[bot] story {index}/{total}: {_FETCH_FAIL_MSG}")
            elif reply:
                await reply(f"[bot] story {index}/{total}: {_FETCH_FAIL_MSG}")
        elif reply:
            await reply(f"[bot] story {index}/{total} failed: {_strip_raw_json(msg)}")
    try:
        _log_run(entry)
    except Exception:
        log.exception("could not write run_log.json")
    return entry["delivered"]


# ── Shared ingestion trigger ──────────────────────────────────────────────────

async def _trigger_ingestion() -> list:
    """Run ingestion in a worker thread. Raises if the candidate list could
    not be delivered to Telegram — the caller must surface that, otherwise
    the bot reports success while the operator never sees a list."""
    candidates = await asyncio.to_thread(
        functools.partial(_ingestion.run, raise_on_send_failure=True)
    )
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

    log.info("/carousel received: %s", url)
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
        log.exception("/carousel failed for %r", url)
        await update.message.reply_text(f"Error: {exc}")
    try:
        _log_run(entry)
    except Exception:
        log.exception("could not write run_log.json")


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_chat(update):
        return
    log.info("/run received from chat %s", update.message.chat_id)
    await update.message.reply_text("[bot] running ingestion...")
    try:
        log.info("ingestion started")
        candidates = await _trigger_ingestion()
        log.info("%d candidates found", len(candidates))
        if not candidates:
            await update.message.reply_text(
                "[bot] ingestion finished with 0 candidates — nothing to approve. "
                "Check sources / API keys if this is unexpected."
            )
            return
        log.info("candidate list sent to Telegram")
        await update.message.reply_text(
            f"[bot] {len(candidates)} candidates sent. "
            "Reply ALL, story numbers (e.g. 1,3), or SKIP (2h window)."
        )
        log.info("waiting for approval...")
    except Exception as exc:
        log.exception("ingestion failed")
        await update.message.reply_text(
            f"[bot] ingestion failed: {exc}\n"
            "No candidate list is pending — fix the issue and /run again."
        )


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


# True while an approved batch is generating — blocks duplicate approvals
# without clearing the pending file before the batch actually completes.
_batch_in_progress = False


async def msg_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _batch_in_progress
    if not _owner_chat(update):
        return

    text = (update.message.text or "").strip()
    if not _looks_like_approval(text):
        return  # ordinary chat message — not an approval attempt

    log.info("approval received: %s", text)
    try:
        # Always re-read state from disk — never trust in-memory state
        pending = _load_pending()
        if not pending:
            log.info("approval arrived but no pending candidates on disk")
            await update.message.reply_text(
                "[bot] No pending candidates — run /run first."
            )
            return

        if _pending_expired(pending):
            _clear_pending()
            log.info("approval window expired — cleared pending")
            await update.message.reply_text(
                "[bot] Approval window expired. Run /run to generate a new candidate list."
            )
            return

        candidates = pending.get("candidates", [])
        result = _parse_approval(text, len(candidates))
        if result is None:
            log.info("approval %r did not parse against %d candidates", text, len(candidates))
            await update.message.reply_text(
                f"[bot] Couldn't match that to the list. Reply ALL, "
                f"story numbers 1–{len(candidates)} (e.g. 1,3), or SKIP."
            )
            return

        if result == "SKIP":
            _clear_pending()
            log.info("run skipped by operator")
            await update.message.reply_text("[bot] run skipped.")
            return

        approved = [candidates[i - 1] for i in result]
        if not approved:
            await update.message.reply_text("[bot] no valid story numbers selected.")
            return

        if _batch_in_progress:
            log.info("approval ignored — a batch is already generating")
            await update.message.reply_text(
                "[bot] A batch is already generating — wait for it to finish."
            )
            return

        log.info("parsed approval: stories %s", result)
        await update.message.reply_text(
            f"[bot] approved {len(approved)} story/stories — generating..."
        )

        _batch_in_progress = True
        delivered = 0
        try:
            for idx, story in enumerate(approved, 1):
                ok = await _carousel_for(
                    story["url"], story["title"], idx, len(approved),
                    update.message.reply_text,
                )
                delivered += 1 if ok else 0
        finally:
            _batch_in_progress = False

        # Clear only after the batch is processed — a crash above leaves the
        # pending file on disk so the operator can approve again.
        _clear_pending()
        log.info("batch complete — %d/%d delivered", delivered, len(approved))
        await update.message.reply_text(
            f"[bot] batch complete — {delivered}/{len(approved)} carousel(s) delivered."
        )
    except Exception as exc:
        log.exception("approval processing failed")
        try:
            await update.message.reply_text(
                f"[bot] approval processing failed: {exc}\n"
                "Pending list kept — reply again to retry, or /run for a fresh list."
            )
        except Exception:
            log.exception("could not report approval failure to Telegram")


# ── Daily scheduled job ───────────────────────────────────────────────────────

async def daily_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    log.info("daily job triggered")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    try:
        log.info("ingestion started")
        candidates = await _trigger_ingestion()
        log.info("%d candidates found", len(candidates))
        if not chat_id:
            log.warning("TELEGRAM_CHAT_ID not set — daily run completed but nobody was notified")
            return
        if not candidates:
            await context.bot.send_message(
                chat_id=chat_id,
                text="[bot] daily run: 0 candidates today — nothing to approve.",
            )
            return
        log.info("candidate list sent to Telegram")
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"[bot] {len(candidates)} candidates above. "
                "Reply ALL, story numbers (e.g. 1,3), or SKIP (2h window)."
            ),
        )
        log.info("waiting for approval...")
    except Exception as exc:
        log.exception("daily job failed")
        if chat_id:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"[bot] Daily run failed: {exc}. Run /run manually to retry.",
                )
            except Exception:
                log.exception("could not send daily-failure message to Telegram")


# ── Global error handler ──────────────────────────────────────────────────────

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for exceptions that escape any handler. Without this, PTB
    swallows handler exceptions with a log line and Telegram stays silent."""
    log.error("unhandled exception in handler", exc_info=context.error)
    target = None
    if isinstance(update, Update) and update.effective_chat:
        target = update.effective_chat.id
    else:
        target = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or None
    if target:
        try:
            await context.bot.send_message(
                chat_id=target, text=f"⚠️ [bot] unhandled error: {context.error}"
            )
        except Exception:
            log.exception("could not report unhandled error to Telegram")


async def _post_init(app: Application) -> None:
    """Announce startup so a crash-restart loop is visible, not silent."""
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not chat_id:
        log.warning("TELEGRAM_CHAT_ID not set — startup message skipped")
        return
    try:
        await app.bot.send_message(
            chat_id=chat_id,
            text=(
                "[bot] online — daily run at 8:00 AM Toronto | /run for manual | "
                "/carousel <url> for on-demand"
            ),
        )
    except Exception:
        log.exception("startup message failed — check TELEGRAM_CHAT_ID / network")


# ── PID lock ─────────────────────────────────────────────────────────────────

def _release_pid_lock() -> None:
    """Remove store/bot.pid, but only if it still belongs to this process."""
    try:
        with open(_PID_PATH) as fh:
            if fh.read().strip() == str(os.getpid()):
                os.remove(_PID_PATH)
    except (FileNotFoundError, OSError, ValueError):
        pass


def _acquire_pid_lock() -> None:
    """Refuse to start if another bot instance is polling — two pollers make
    Telegram return 409 Conflict and updates get lost intermittently.
    A stale PID file (LaunchAgent restart after a crash) is taken over."""
    os.makedirs(_STORE_DIR, exist_ok=True)
    if os.path.exists(_PID_PATH):
        old_pid = None
        try:
            with open(_PID_PATH) as fh:
                old_pid = int(fh.read().strip())
        except (ValueError, OSError):
            pass
        if old_pid and old_pid != os.getpid():
            try:
                os.kill(old_pid, 0)  # signal 0 = existence check only
            except ProcessLookupError:
                log.info("stale bot.pid (pid %d not running) — taking over", old_pid)
            except PermissionError:
                sys.exit(
                    f"[bot] another instance appears to be running (pid {old_pid}, "
                    "store/bot.pid, owned by a different user). Stop it first."
                )
            else:
                sys.exit(
                    f"[bot] another instance is already running (pid {old_pid}, store/bot.pid).\n"
                    "Two instances cause Telegram 409 Conflict and dropped updates.\n"
                    "Stop the LaunchAgent first: launchctl unload "
                    "~/Library/LaunchAgents/com.frameshift.bot.plist\n"
                    "or remove store/bot.pid if you are sure it is stale."
                )
    with open(_PID_PATH, "w") as fh:
        fh.write(str(os.getpid()))
    atexit.register(_release_pid_lock)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        sys.exit("[bot] TELEGRAM_BOT_TOKEN not set — check .env")

    _acquire_pid_lock()

    import pytz
    toronto_tz = pytz.timezone(_TIMEZONE)

    app = Application.builder().token(token).post_init(_post_init).build()
    app.add_handler(CommandHandler("carousel", cmd_carousel))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("substack", cmd_substack))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_approval))
    app.add_error_handler(on_error)

    if app.job_queue is None:
        sys.exit(
            "[bot] job queue unavailable — the daily scheduler cannot run.\n"
            "Install the scheduler extra: pip3 install 'python-telegram-bot[job-queue]'"
        )

    run_time = dt_time(_DAILY_HOUR, _DAILY_MINUTE, tzinfo=toronto_tz)
    # misfire_grace_time=3600: fire the job even if the event loop was busy at the exact second
    job = app.job_queue.run_daily(daily_job, time=run_time, name="daily_ingestion",
                                  job_kwargs={"misfire_grace_time": 3600})

    # job.next_t no longer exists on PTB v20+ — compute from the APScheduler
    # trigger (job.job is the underlying APScheduler job; before the scheduler
    # starts, next_run_time is not yet populated).
    try:
        next_run = job.job.trigger.get_next_fire_time(None, datetime.now(toronto_tz))
    except Exception:
        next_run = f"daily {_DAILY_HOUR:02d}:{_DAILY_MINUTE:02d} {_TIMEZONE}"

    print(f"[bot] starting — on-demand: /carousel <url> | daily: 8:00 AM Toronto")
    print(f"[bot] scheduler armed — next run: {next_run}")
    print("[bot] polling... (Ctrl+C to stop)")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
