"""
Frameshift v2 — watcher/image_fetcher.py
Fetch cover images: OG image from article URL, Pexels search, or FLUX generation fallback.

Public API:
    get_cover_image(og_image_url, image_query) → PIL.Image or None
"""
from __future__ import annotations

import base64
import io
import os
import sys

import requests
from dotenv import load_dotenv
from PIL import Image

_ENV_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
)
load_dotenv(_ENV_PATH)

_FLUX_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "black-forest-labs/FLUX.1-schnell/v1/images/generations"
)
_PEXELS_URL = "https://api.pexels.com/v1/search"
_MIN_WIDTH  = 400
_MIN_HEIGHT = 300


def fetch_og_image(url: str) -> Image.Image | None:
    """GET the image at url, validate dimensions, return RGB PIL Image or None."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        if img.width < _MIN_WIDTH or img.height < _MIN_HEIGHT:
            print(f"[image] OG image too small ({img.width}x{img.height}), discarding", file=sys.stderr)
            return None
        print(f"[image] fetched OG image {img.width}x{img.height} from {url}", file=sys.stderr)
        return img
    except Exception as exc:
        print(f"[image] OG image failed: {exc}", file=sys.stderr)
        return None


def fetch_pexels_image(query: str) -> Image.Image | None:
    """Search Pexels for a portrait image matching query, return RGB PIL Image or None."""
    api_key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not api_key:
        print("[image] PEXELS_API_KEY not set — skipping Pexels", file=sys.stderr)
        return None
    try:
        resp = requests.get(
            _PEXELS_URL,
            headers={"Authorization": api_key},
            params={"query": query, "per_page": 1, "orientation": "portrait"},
            timeout=10,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            print(f"[image] Pexels returned no results for: {query[:50]}", file=sys.stderr)
            return None
        img_url = photos[0]["src"]["large2x"]
        img_resp = requests.get(img_url, timeout=15)
        img_resp.raise_for_status()
        img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        print(f"[image] fetched Pexels image for query: {query[:50]}", file=sys.stderr)
        return img
    except Exception as exc:
        print(f"[image] Pexels failed: {exc}", file=sys.stderr)
        return None


def fetch_flux_image(prompt: str) -> Image.Image | None:
    """Generate an image via FLUX.1-schnell on HuggingFace. Rotates through 3 API keys on 429."""
    keys = [
        os.environ.get("HF_API_KEY",   "").strip(),
        os.environ.get("HF_API_KEY_2", "").strip(),
        os.environ.get("HF_API_KEY_3", "").strip(),
    ]
    keys = [k for k in keys if k]
    if not keys:
        print("[image] HF_API_KEY not set — FLUX fallback disabled", file=sys.stderr)
        return None

    payload = {"prompt": prompt, "num_inference_steps": 4}
    for i, key in enumerate(keys):
        try:
            resp = requests.post(
                _FLUX_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
            if resp.status_code == 429:
                print(f"[image] FLUX 429 on key {i + 1}, trying next...", file=sys.stderr)
                continue
            resp.raise_for_status()
            b64 = resp.json()["data"][0]["b64_json"]
            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            print(f"[image] FLUX generated image for prompt: {prompt[:50]}", file=sys.stderr)
            return img
        except Exception as exc:
            print(f"[image] FLUX error on key {i + 1}: {exc}", file=sys.stderr)
            continue
    return None


def get_cover_image(og_image_url: str | None, image_query: str) -> Image.Image | None:
    """
    Priority: OG image → Pexels search → FLUX generation → None.
    Renderer uses dark placeholder when None is returned.
    """
    if og_image_url:
        img = fetch_og_image(og_image_url)
        if img is not None:
            print("[image] using OG image for cover", file=sys.stderr)
            return img

    if image_query:
        img = fetch_pexels_image(image_query)
        if img is not None:
            print("[image] using Pexels image for cover", file=sys.stderr)
            return img

        img = fetch_flux_image(image_query)
        if img is not None:
            print("[image] using FLUX image for cover", file=sys.stderr)
            return img

    print("[image] no cover image — renderer will use dark placeholder", file=sys.stderr)
    return None
