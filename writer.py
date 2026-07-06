"""
Frameshift v2 — Writer
Scrapes an article URL and calls Gemini 2.5 Flash to produce structured
carousel JSON that renderer.py can consume directly.

Usage:
    python3 writer.py https://some-article-url
"""

import json
import os
import sys

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# ── MODEL ─────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"

# ── CONTENT SLIDES allowed between cover and cta ─────────────────────────────
_CONTENT_TYPES = {"stat", "quote", "context", "contrast", "timeline", "explainer", "signal"}

# ── PROMPTS ───────────────────────────────────────────────────────────────────
SYSTEM_INSTRUCTION = (
    "You are a carousel editor for The Frameshift, an intelligence publication "
    "covering AI, spatial computing, AR, and emerging technology. "
    "You write for a technically literate Instagram audience — not specialists, "
    "but people who follow the space closely. "
    "You are precise, opinionated, and concise. You never invent facts. "
    "When the source does not support a claim, you omit the slide rather than fabricate."
)

USER_PROMPT_TEMPLATE = """\
Produce a carousel for the article below.
Output VALID JSON ONLY — no markdown fences, no preamble, no commentary.

═══════════════════════════════════════════════════════
SLIDE STRUCTURE
═══════════════════════════════════════════════════════
  • First slide : always "cover"
  • Middle slides: 2–6 slides chosen from the palette (never more than 2 of the same type)
  • Last slide  : always "cta"

═══════════════════════════════════════════════════════
SLIDE PALETTE
═══════════════════════════════════════════════════════
  stat      — use when a single number reframes the story
  quote     — use when a direct quote carries more weight than paraphrase
  context   — use when the reader needs to know what happened before anything else
  contrast  — use when two competing things are the core tension
  timeline  — use when sequence and momentum matter
  explainer — use when the reader needs a concept explained before the point lands
  signal    — use for one forward-looking implication

═══════════════════════════════════════════════════════
RULES
═══════════════════════════════════════════════════════
  1. A thin story needs only 2 middle slides — do not pad
  2. Never use more than 2 of the same slide type
  3. Every claim must be grounded in the article — if the source doesn't support it, omit that slide
  4. All word limits are hard limits — do not exceed them
  5. cover and cta are always included; never add extra copies of either

═══════════════════════════════════════════════════════
JSON SCHEMA  (produce exactly these fields per slide type)
═══════════════════════════════════════════════════════

cover:
  {{"type":"cover","headline":"<str, max 12 words>","category":"<str, max 4 words, UPPERCASE>","image_query":"<str, 5-8 words for image search>"}}

stat:
  {{"type":"stat","eyebrow":"<str, max 4 words>","number":"<str, e.g. '$14B' or '73%'>","unit":"<str, max 8 words>","context":"<str, max 35 words>"}}

quote:
  {{"type":"quote","text":"<str, max 40 words>","attribution":"<str, Name, Title — Organisation>"}}

context:
  {{"type":"context","kicker":"<str, max 3 words>","headline":"<str, max 15 words>","body":"<str, max 40 words>","use_image":<bool>}}

contrast:
  {{"type":"contrast","kicker":"<str, max 3 words>","label_a":"<str, max 3 words>","value_a":"<str, max 20 words>","label_b":"<str, max 3 words>","value_b":"<str, max 20 words>","takeaway":"<str, max 25 words>"}}

timeline:
  {{"type":"timeline","kicker":"<str, max 3 words>","events":[{{"date":"<str>","event":"<str, max 12 words>"}}, ...]}}

explainer:
  {{"type":"explainer","kicker":"<str, max 3 words>","question":"<str, max 15 words>","answer":"<str, max 55 words>"}}

signal:
  {{"type":"signal","kicker":"<str, max 3 words>","headline":"<str, max 15 words>","implication":"<str, max 45 words>","tag":"<str, max 4 words>"}}

cta:
  {{"type":"cta","headline":"<str, max 20 words — story-specific follow hook>"}}

═══════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════
{{
  "slides": [
    {{"type": "cover", ...}},
    ...middle slides in narrative order...,
    {{"type": "cta", ...}}
  ]
}}

═══════════════════════════════════════════════════════
ARTICLE TITLE: {title}

ARTICLE:
{body}
"""


# ── STEP 1: SCRAPE ────────────────────────────────────────────────────────────

def scrape(url: str) -> dict:
    """
    Fetch article at url. Returns {title, body, og_image_url}.
    Raises ValueError if the fetch fails or body is under 200 chars.
    """
    try:
        resp = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FrameshiftBot/2.0)"},
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"fetch failed for {url!r}: {exc}") from exc

    soup = BeautifulSoup(resp.text, "html.parser")

    # title
    og_title = soup.find("meta", property="og:title")
    title = (og_title["content"] if og_title else None) or (
        soup.title.string.strip() if soup.title else ""
    )

    # og:image
    og_img = soup.find("meta", property="og:image")
    og_image_url = og_img["content"].strip() if og_img and og_img.get("content") else None

    # body — collect <p> tags, drop boilerplate fragments
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text(separator=" ", strip=True)
        # drop very short fragments (nav links, single words, etc.)
        if len(text) < 40:
            continue
        paragraphs.append(text)

    body = "\n\n".join(paragraphs)

    if len(body) < 200:
        raise ValueError(
            f"body too short ({len(body)} chars) after extraction from {url!r} — "
            "page may be paywalled, JavaScript-rendered, or empty"
        )

    return {"title": title, "body": body, "og_image_url": og_image_url}


# ── STEP 2: WRITE ─────────────────────────────────────────────────────────────

def write(article_dict: dict) -> list:
    """
    Call Gemini 2.5 Flash with article content.
    Returns validated slides list.
    Raises ValueError on API error, JSON parse failure, or schema validation failure.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    prompt = USER_PROMPT_TEMPLATE.format(
        title=article_dict.get("title", "(no title)"),
        body=article_dict.get("body", ""),
    )

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
    except Exception as exc:
        raise ValueError(f"Gemini API call failed: {exc}") from exc

    # strip accidental markdown fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned invalid JSON: {exc}\n\n--- RAW RESPONSE ---\n{raw}"
        ) from exc

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) == 0:
        raise ValueError(
            f"response missing 'slides' array\n\n--- RAW RESPONSE ---\n{raw}"
        )

    if slides[0].get("type") != "cover":
        raise ValueError(
            f"first slide must be 'cover', got {slides[0].get('type')!r}\n\n--- RAW RESPONSE ---\n{raw}"
        )

    if slides[-1].get("type") != "cta":
        raise ValueError(
            f"last slide must be 'cta', got {slides[-1].get('type')!r}\n\n--- RAW RESPONSE ---\n{raw}"
        )

    middle = slides[1:-1]
    if not (2 <= len(middle) <= 6):
        raise ValueError(
            f"expected 2–6 middle slides, got {len(middle)}\n\n--- RAW RESPONSE ---\n{raw}"
        )

    unknown = [s.get("type") for s in middle if s.get("type") not in _CONTENT_TYPES]
    if unknown:
        raise ValueError(
            f"unknown slide type(s) in middle: {unknown}\n\n--- RAW RESPONSE ---\n{raw}"
        )

    return slides


# ── STEP 3: GENERATE ──────────────────────────────────────────────────────────

def generate(url: str) -> dict:
    """
    Full pipeline: scrape → write.
    Returns {slides: [...], og_image_url: str | None}.
    """
    print(f"[writer] scraping {url} ...")
    article = scrape(url)

    print(f"[writer] writing carousel ({len(article['body'])} chars scraped) ...")
    slides = write(article)

    print(f"[writer] done ({len(slides)} slides)")
    return {"slides": slides, "og_image_url": article["og_image_url"]}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 writer.py <url>", file=sys.stderr)
        sys.exit(1)

    result = generate(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
