"""
Frameshift v2 — watcher/delivery.py
Sends a rendered carousel to Telegram as a media group.

Usage (CLI smoke test):
    python3 watcher/delivery.py --url https://example.com slide_01.png slide_02.png ...
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import Bot, InputMediaPhoto

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(os.path.normpath(_ENV_PATH))

_STORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "store")
_DELIVERED_LOG = os.path.join(_STORE_DIR, "delivered.json")


async def _send_async(png_paths: list, caption: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set — check ~/frameshift_v2/.env")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID is not set — check ~/frameshift_v2/.env")

    bot = Bot(token=token)
    media = []
    for i, path in enumerate(png_paths):
        with open(path, "rb") as fh:
            data = fh.read()
        media.append(InputMediaPhoto(media=data, caption=caption if i == 0 else ""))

    await bot.send_media_group(chat_id=chat_id, media=media)


def _log_delivery(png_paths: list, source_url: str, slide_count: int) -> None:
    os.makedirs(_STORE_DIR, exist_ok=True)
    try:
        with open(_DELIVERED_LOG) as fh:
            log = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        log = []

    log.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_url": source_url,
        "slide_count": slide_count,
        "files": [os.path.basename(p) for p in png_paths],
    })

    with open(_DELIVERED_LOG, "w") as fh:
        json.dump(log, fh, indent=2)


def _break_caption(text: str) -> str:
    """Split caption into 2-sentence paragraphs separated by blank lines."""
    sentences = re.split(r'(?<=[.!?]) +(?=[A-Z])', text.strip())
    pairs = [" ".join(sentences[i:i + 2]) for i in range(0, len(sentences), 2)]
    return "\n\n".join(pairs)


def send(png_paths: list, data: dict, source_url: str) -> dict:
    """
    Send rendered PNGs to Telegram as a media group.

    Args:
        png_paths:  Ordered list of PNG file paths (output of render_carousel).
        data:       Full writer.generate() output: {"slides", "caption", "og_image_url"}.
        source_url: Original article URL; appended to caption.

    Returns:
        {"sent": int, "chat_id": str}
    """
    if not png_paths:
        raise ValueError("png_paths is empty — nothing to send")

    caption = f"{_break_caption(data['caption'])}\n\n{source_url}"
    print(f"[delivery] caption: {caption!r}")
    print(f"[delivery] slide count: {len(png_paths)}")
    print(f"[delivery] first png: {png_paths[0] if png_paths else 'NONE'}")
    print(f"[delivery] sending {len(png_paths)} slides to Telegram...")
    asyncio.run(_send_async(png_paths, caption))
    _log_delivery(png_paths, source_url, len(data["slides"]))

    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    print(f"[delivery] done — {len(png_paths)} slides sent to {chat_id}")
    return {"sent": len(png_paths), "chat_id": chat_id}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send carousel PNGs to Telegram.")
    parser.add_argument("pngs", nargs="+", help="PNG file paths to send")
    parser.add_argument("--url", default="", help="Source article URL for caption")
    args = parser.parse_args()

    stub_data = {"slides": [], "caption": "", "og_image_url": None}
    result = send(args.pngs, stub_data, args.url)
    print(json.dumps(result, indent=2))
