"""
Frameshift v2 — watcher/logo_fetcher.py
Detect company mentions in cover slide fields and fetch logos.

Public API:
    get_company_logo(headline, category) → PIL.Image or None
"""
from __future__ import annotations

import io
import os
import sys

import requests
from PIL import Image

COMPANY_DOMAINS = {
    "openai": "openai.com",
    "anthropic": "anthropic.com",
    "meta": "meta.com",
    "google": "google.com",
    "deepmind": "deepmind.com",
    "microsoft": "microsoft.com",
    "apple": "apple.com",
    "nvidia": "nvidia.com",
    "spacex": "spacex.com",
    "snap": "snap.com",
    "snapchat": "snap.com",
    "amazon": "amazon.com",
    "aws": "amazon.com",
    "tesla": "tesla.com",
    "xreal": "xreal.com",
    "asus": "asus.com",
    "samsung": "samsung.com",
    "qualcomm": "qualcomm.com",
    "huawei": "huawei.com",
    "bytedance": "bytedance.com",
    "tiktok": "bytedance.com",
    "coinbase": "coinbase.com",
    "mistral": "mistral.ai",
    "hugging face": "huggingface.co",
    "huggingface": "huggingface.co",
    "waymo": "waymo.com",
    "boston dynamics": "bostondynamics.com",
    "byd": "byd.com",
}

LOCAL_LOGO_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "logos")
)

_MAX_W = 200
_MAX_H = 80


def detect_company(headline: str, category: str) -> str | None:
    """Return the first known company key found in headline + category, or None."""
    text = (headline + " " + category).lower()
    for company in COMPANY_DOMAINS:
        if company in text:
            return company
    return None


def fetch_clearbit_logo(domain: str) -> Image.Image | None:
    """Fetch logo via Google S2 favicon service (free, no token). Returns RGBA PIL Image or None."""
    url = f"https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{domain}&size=256"
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and len(resp.content) > 500:
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            print(f"[logo] fetched logo for {domain}", file=sys.stderr)
            return img
    except Exception as exc:
        print(f"[logo] logo fetch failed for {domain}: {exc}", file=sys.stderr)
    return None


def fetch_local_logo(company: str) -> Image.Image | None:
    """Check assets/logos/{company}.png. Returns RGBA PIL Image or None."""
    path = os.path.join(LOCAL_LOGO_DIR, f"{company.replace(' ', '_')}.png")
    if os.path.exists(path):
        try:
            img = Image.open(path).convert("RGBA")
            print(f"[logo] using local logo for {company}", file=sys.stderr)
            return img
        except Exception:
            pass
    return None


def get_company_logo(headline: str, category: str) -> Image.Image | None:
    """
    Detect company in headline/category, fetch via Clearbit then local fallback.
    Returns RGBA PIL Image scaled to max 200×80px, or None.
    """
    company = detect_company(headline, category)
    if not company:
        return None

    domain = COMPANY_DOMAINS[company]
    logo = fetch_clearbit_logo(domain) or fetch_local_logo(company)

    if logo is None:
        print(f"[logo] no logo found for {company}", file=sys.stderr)
        return None

    ratio = min(_MAX_W / logo.width, _MAX_H / logo.height)
    new_size = (int(logo.width * ratio), int(logo.height * ratio))
    return logo.resize(new_size, Image.LANCZOS)
