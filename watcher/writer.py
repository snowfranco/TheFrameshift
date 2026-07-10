"""
Frameshift v2 — watcher/writer.py
Scrapes an article URL and calls Gemini 2.5 Flash to produce a structured
carousel JSON that renderer.py can consume directly.

Usage:
    python3 watcher/writer.py https://some-article-url
"""

import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Ensure this directory is importable regardless of invocation path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from design_constants import WRITER_PROMPT  # noqa: E402
from image_fetcher import get_cover_image, fetch_pexels_image   # noqa: E402
from logo_fetcher import get_company_logo   # noqa: E402
from renderer import RENDERERS              # noqa: E402

# Load .env from the project root, not cwd
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(os.path.normpath(_ENV_PATH))

NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
_GROQ_FALLBACK_MODEL = "llama-3.1-70b-versatile"
_SYSTEM_INSTRUCTION = (
    "You are a carousel editor for The Frameshift Instagram account, covering AI, "
    "spatial computing, AR, and emerging technology. Respond only with valid JSON. "
    "No markdown fences. No preamble."
)

# Injected between the palette instructions and the article — forces exact field names
_SCHEMA_ENFORCEMENT = (
    "REQUIRED FIELDS PER SLIDE TYPE — use EXACTLY these field names, no alternatives:\n\n"
    "cover:     headline (str), category (str), image_query (str)\n"
    "stat:      eyebrow (str), number (str), unit (str), context (str)\n"
    "quote:     text (str), attribution (str)\n"
    "context:   kicker (str), headline (str), body (str), use_image (bool)\n"
    "contrast:  kicker (str), label_a (str), value_a (str), label_b (str), value_b (str), takeaway (str)\n"
    'timeline:  kicker (str), events (list of {"date": str, "event": str})\n'
    "explainer: kicker (str), question (str), answer (str)\n"
    "signal:    kicker (str), headline (str), implication (str), tag (str)\n"
    "cta:       headline (str) — required, ALWAYS the last slide\n"
    "TOP-LEVEL FIELD (alongside 'slides', not inside any slide):\n"
    "caption: (str) 3-4 sentence Instagram caption. "
    "MINIMUM 50 words. Lead with the most interesting fact. "
    "Explain why it matters. Third person. Factual. No hype. "
    "Do NOT just restate the headline. "
    "TOP-LEVEL field alongside slides, not inside any slide.\n\n"
    "CTA SLIDE — required, always last:\n"
    "cta.headline: story-specific reason to follow @ai.xr.frameshift. "
    "Must reference what The Frameshift covers, not the article topic. "
    "Example: 'We track every AR acquisition before it goes mainstream.' "
    "NOT: 'Learn more about Snap's AR efforts'. "
    "It is a follow hook, never a source tagline or article summary.\n\n"
    "QUALITY RULES — these override the palette rules above:\n"
    "- signal.implication: minimum 25 words. Must make a specific "
    "forward-looking claim. No hedging language ('could', 'might', "
    "'has potential'). State what WILL happen or IS happening.\n"
    "- stat: only use when the number is surprising, large, or reframes "
    "the story's significance. 12% revenue growth is not a stat slide. "
    "$14B market size is. If no strong stat exists, omit this slide type "
    "entirely.\n"
    "- context.body: minimum 30 words. Must explain what happened AND why "
    "it matters in one paragraph.\n\n"
    "CRITICAL — do not substitute field names:\n"
    '- "headline" not "title" (applies to cover, context, signal, cta)\n'
    '- "attribution" not "source", "author", or "by" (quote slide)\n'
    '- "body" not "text" or "description" (context slide)\n'
    '- "implication" not "text" or "body" (signal slide)\n\n'
    "OVERRIDE OUTPUT FORMAT — use this exact structure:\n"
    '{\n'
    '  "caption": "3-4 sentences here, minimum 50 words, lead with the most interesting fact and explain why it matters...",\n'
    '  "slides": [\n'
    '    {"type": "cover", ...cover fields},\n'
    '    ...content slides in narrative order...,\n'
    '    {"type": "cta", "headline": "story-specific follow hook"}\n'
    '  ]\n'
    '}\n'
)
GEMINI_MODEL = "gemini-2.0-flash"
_GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

_HASHTAG_PROMPT = (
    "You are an Instagram hashtag strategist for @ai.xr.frameshift, "
    "an AI and emerging tech account with a contrarian, practical editorial voice.\n\n"
    "Generate exactly 5 high-performing Instagram hashtags for this article. "
    "Mix: 1-2 broad niche tags (#AITools, #ArtificialIntelligence, #TechNews), "
    "2-3 topic-specific tags based on the article content, "
    "and 0-1 trend or event tag if clearly relevant.\n\n"
    "Rules:\n"
    "- Return ONLY the 5 hashtags on a single line, space-separated\n"
    "- Each hashtag starts with # and has no spaces inside\n"
    "- No explanation, no numbering, no punctuation besides #\n"
    "- Avoid overly generic tags like #Tech or #AI alone\n\n"
    "Article title: {title}\n"
    "Article excerpt: {excerpt}"
)

_DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
    "Mobile/15E148 Safari/604.1"
)
_SCRAPE_HEADERS = {
    "User-Agent": _DESKTOP_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
}


# ── HASHTAG GENERATION ───────────────────────────────────────────────────────

def _generate_hashtags(title: str, body: str) -> str:
    """
    Generate 5 Instagram hashtags via Groq (same key used for carousel generation).
    Returns a space-separated hashtag string. Returns '' on any failure.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return ""

    prompt = _HASHTAG_PROMPT.format(title=title, excerpt=body[:600])
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 60,
    }
    try:
        resp = requests.post(
            _GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if resp.status_code == 429:
            return ""
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        tags = [t for t in raw.split() if t.startswith("#") and len(t) > 1]
        return " ".join(tags[:5])
    except Exception:
        return ""


# ── STEP 1: SCRAPE ────────────────────────────────────────────────────────────

def _extract_body(soup: BeautifulSoup) -> tuple:
    """Try extraction strategies in order. Returns (text, strategy_label) or ('', 'none')."""
    _CONTENT_CLASSES = {"article", "content", "story", "body", "post", "entry"}

    # 1. <p> tags
    body = " ".join(p.get_text(separator=" ", strip=True) for p in soup.find_all("p")).strip()
    if len(body) >= 200:
        return body[:6000], "<p> tags"

    # 2a. <article> tag
    tag = soup.find("article")
    if tag:
        body = tag.get_text(separator=" ", strip=True)
        if len(body) >= 200:
            return body[:6000], "article tag"

    # 2b. <div> with class containing content keywords
    for div in soup.find_all("div", class_=True):
        if any(kw in " ".join(div.get("class", [])).lower() for kw in _CONTENT_CLASSES):
            body = div.get_text(separator=" ", strip=True)
            if len(body) >= 200:
                return body[:6000], f"div.{div['class'][0]}"

    # 2c. <main> tag
    tag = soup.find("main")
    if tag:
        body = tag.get_text(separator=" ", strip=True)
        if len(body) >= 200:
            return body[:6000], "main tag"

    # 2d. largest div block
    best_text = ""
    for div in soup.find_all("div"):
        text = div.get_text(separator=" ", strip=True)
        if len(text) > len(best_text):
            best_text = text
    if len(best_text) >= 200:
        return best_text[:6000], "largest div block"

    return "", "none"


def scrape(url: str) -> dict:
    """
    Fetch the article at url.
    Returns {"title": str, "body": str, "og_image_url": str | None}.
    Raises ValueError if body is under 200 chars after all strategies.
    """
    title = ""
    og_image_url = None
    body = ""

    session = requests.Session()
    session.headers.update(_SCRAPE_HEADERS)

    try:
        resp = session.get(url, timeout=15)
    except requests.RequestException as exc:
        raise ValueError(f"Request failed for {url!r}: {exc}") from exc

    if resp.status_code != 200:
        print(
            f"[scraper] HTTP {resp.status_code} — trying Jina fallback",
            file=sys.stderr,
        )
    else:
        soup = BeautifulSoup(resp.text, "html.parser")

        # title: og:title → <title>
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        # og:image
        og_img = soup.find("meta", property="og:image")
        og_image_url = (
            og_img["content"].strip()
            if og_img and og_img.get("content")
            else None
        )

        body, strategy = _extract_body(soup)

        if len(body) >= 200:
            print(f"[scraper] extracted via {strategy} ({len(body)} chars)", file=sys.stderr)
        else:
            # Mobile UA fallback — some sites serve lighter pages that are easier to parse
            session.headers.update({"User-Agent": _MOBILE_UA})
            try:
                mobile_resp = session.get(url, timeout=15)
                if mobile_resp.status_code != 200:
                    print(
                        f"[scraper] mobile UA got HTTP {mobile_resp.status_code} — trying Jina fallback",
                        file=sys.stderr,
                    )
                else:
                    mobile_soup = BeautifulSoup(mobile_resp.text, "html.parser")
                    body, strategy = _extract_body(mobile_soup)
                    if len(body) >= 200:
                        print(
                            f"[scraper] extracted via mobile UA fallback ({len(body)} chars)",
                            file=sys.stderr,
                        )
            except requests.RequestException:
                pass

    if len(body) < 200:
        # Jina Reader API fallback — handles 403s and JS-rendered pages
        try:
            jina_resp = requests.get(
                f"https://r.jina.ai/{url}",
                headers={"Accept": "text/plain"},
                timeout=15,
            )
            if jina_resp.status_code == 200 and len(jina_resp.text) > 200:
                jina_text = jina_resp.text.strip()

                # Extract title from "Title: ..." metadata line
                jina_title = ""
                for line in jina_text.splitlines():
                    if line.startswith("Title:"):
                        jina_title = line[len("Title:"):].strip()
                        break

                # Skip metadata header lines, use remaining text as body
                _JINA_SKIP = ("Title:", "URL Source:", "Published Time:",
                              "Markdown Content:", "Published")
                body_lines = []
                past_header = False
                for line in jina_text.splitlines():
                    if not past_header:
                        if not line.strip() or any(line.strip().startswith(p) for p in _JINA_SKIP):
                            continue
                        past_header = True
                    body_lines.append(line)

                # Strip basic markdown formatting
                jina_body = "\n".join(body_lines)
                jina_body = re.sub(r"^#{1,6}\s+", "", jina_body, flags=re.MULTILINE)
                jina_body = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", jina_body)
                jina_body = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", jina_body)
                jina_body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", jina_body)
                jina_body = re.sub(r"^[-*_]{3,}\s*$", "", jina_body, flags=re.MULTILINE)
                jina_body = re.sub(r"^>\s*", "", jina_body, flags=re.MULTILINE)
                jina_body = jina_body.strip()[:6000]

                if len(jina_body) >= 200:
                    if jina_title and not title:
                        title = jina_title
                    body = jina_body
                    print(
                        f"[scraper] extracted via Jina Reader API ({len(body)} chars)",
                        file=sys.stderr,
                    )
        except requests.RequestException:
            pass

    if body:
        body = body.replace('\x00', '')
        body = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', body)
        body = body.encode('utf-8', errors='ignore').decode('utf-8')
        body = body[:6000]

    if len(body) < 200:
        if resp.status_code != 200:
            raise ValueError(
                f"Could not fetch article: HTTP {resp.status_code}. "
                "Jina fallback also failed."
            )
        raise ValueError(
            f"Body too short after all extraction strategies ({len(body)} chars) from {url!r}. "
            "Tried: <p> tags, article tag, div content class, main tag, largest div block, "
            "mobile UA fallback, Jina Reader API. "
            "Page may be paywalled, JavaScript-rendered, or empty."
        )

    return {"title": title, "body": body, "og_image_url": og_image_url}


# ── STEP 2: WRITE ─────────────────────────────────────────────────────────────

def write(article: dict) -> dict:
    """
    Call Groq (llama-3.3-70b-versatile) with the article content.
    Returns {"slides": list, "caption": str} — slides end with a cta slide.
    Raises ValueError on API failure, JSON parse error, or schema violation.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set — check ~/frameshift_v2/.env")

    article_text = article["title"] + "\n\n" + article["body"]
    # Inject schema enforcement block between the palette instructions and the article
    prompt = WRITER_PROMPT.replace(
        "ARTICLE:\n{{article_text}}",
        _SCHEMA_ENFORCEMENT + "\nARTICLE:\n" + article_text,
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_INSTRUCTION},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    _headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    print(f"[writer] {GROQ_MODEL}...", file=sys.stderr)
    try:
        resp = requests.post(_GROQ_API_URL, headers=_headers, json=payload, timeout=60)
        if resp.status_code == 429:
            wait = 15.0
            m = re.search(r"Please try again in (\d+(?:\.\d+)?)s", resp.text)
            if m:
                wait = float(m.group(1)) + 1.0
            print(f"[writer] Groq 429 — waiting {wait:.0f}s and retrying...", file=sys.stderr)
            time.sleep(wait)
            resp = requests.post(_GROQ_API_URL, headers=_headers, json=payload, timeout=60)
        if resp.status_code == 429:
            print(f"[writer] falling back to {_GROQ_FALLBACK_MODEL}", file=sys.stderr)
            payload["model"] = _GROQ_FALLBACK_MODEL
            resp = requests.post(_GROQ_API_URL, headers=_headers, json=payload, timeout=60)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError) as exc:
        raise ValueError(f"Groq API call failed: {exc}") from exc

    # Defensively strip markdown fences if the model wraps output anyway
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(ln for ln in lines if not ln.startswith("```")).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid carousel JSON: could not parse response — {exc}\n\nRaw: {raw}"
        ) from exc

    slides = data.get("slides")
    caption = (data.get("caption") or "").strip()

    if not isinstance(slides, list) or not slides:
        raise ValueError(
            f"Invalid carousel JSON: 'slides' key missing or empty\n\nRaw: {raw}"
        )

    if slides[0].get("type") != "cover":
        raise ValueError(
            f"Invalid carousel JSON: first slide must be 'cover', "
            f"got {slides[0].get('type')!r}\n\nRaw: {raw}"
        )

    # cta is required as the LAST slide. Drop any stray mid-list cta the
    # model emits; if it omitted the final cta, append a brand-default so
    # the carousel never ships without a follow hook.
    last = slides[-1]
    slides = [s for s in slides[:-1] if s.get("type") != "cta"] + [last]
    if last.get("type") != "cta":
        print("[writer] model omitted cta slide — appending default follow hook", file=sys.stderr)
        slides = slides + [{
            "type": "cta",
            "headline": "We track AI and spatial computing before it goes mainstream. Follow along.",
        }]

    middle = slides[1:-1]
    if not (2 <= len(middle) <= 6):
        raise ValueError(
            f"Invalid carousel JSON: expected 2–6 middle slides, "
            f"got {len(middle)}\n\nRaw: {raw}"
        )

    valid_types = set(RENDERERS.keys())
    for slide in slides:
        stype = slide.get("type")
        if stype not in valid_types:
            raise ValueError(
                f"Invalid carousel JSON: unknown slide type {stype!r} "
                f"(valid: {sorted(valid_types)})\n\nRaw: {raw}"
            )

    # Minimum text length — guard against empty/near-empty LLM output
    # Per-field overrides for short-value fields; default floor is 3
    _FIELD_MIN = {"number": 1, "tag": 1, "unit": 1, "category": 2}
    for slide in slides:
        stype = slide.get("type", "unknown")
        for field, value in slide.items():
            if field == "type" or not isinstance(value, str):
                continue
            min_len = _FIELD_MIN.get(field, 3)
            if len(value.strip()) < min_len:
                raise ValueError(
                    f"Invalid carousel JSON: {stype}.{field} is too short "
                    f"({len(value.strip())} chars, minimum {min_len})\n\nRaw: {raw}"
                )

    if len(caption) < 80:
        raise ValueError(
            f"Invalid carousel JSON: caption must be at least 80 characters, "
            f"got {len(caption)} chars\n\nRaw: {raw}"
        )

    _warn_on_quality(slides)

    return {"slides": slides, "caption": caption}


# Quality floors are enforced in the prompt; here they only WARN (stderr →
# bot.error.log) so drift is observable without killing a deliverable carousel.
_HEDGING_PHRASES = ("could ", "might ", "may ", "has potential", "have potential")


def _warn_on_quality(slides: list) -> None:
    for slide in slides:
        stype = slide.get("type")
        if stype == "signal":
            impl = slide.get("implication", "")
            wc = len(impl.split())
            if wc < 25:
                print(
                    f"[writer] QUALITY WARNING: signal.implication is {wc} words "
                    "(minimum 25)", file=sys.stderr,
                )
            if any(h in impl.lower() for h in _HEDGING_PHRASES):
                print(
                    "[writer] QUALITY WARNING: signal.implication uses hedging "
                    "language ('could'/'might'/'has potential')", file=sys.stderr,
                )
        elif stype == "context":
            wc = len(slide.get("body", "").split())
            if wc < 30:
                print(
                    f"[writer] QUALITY WARNING: context.body is {wc} words "
                    "(minimum 30)", file=sys.stderr,
                )


# ── STEP 3: GENERATE ──────────────────────────────────────────────────────────

def generate(url: str) -> dict:
    """
    Full pipeline: scrape → write.
    Returns {"slides": list, "og_image_url": str | None}.
    """
    print(f"[writer] scraping {url}...", file=sys.stderr)
    article = scrape(url)

    print("[writer] writing...", file=sys.stderr)
    result = write(article)

    print("[writer] generating hashtags...", file=sys.stderr)
    hashtags = _generate_hashtags(article["title"], article["body"])
    if hashtags:
        result["caption"] = result["caption"] + "\n\n" + hashtags
        print(f"[writer] hashtags: {hashtags}", file=sys.stderr)

    print(f"[writer] done ({len(result['slides'])} slides)", file=sys.stderr)

    cover_slide = next(s for s in result["slides"] if s["type"] == "cover")
    image_obj = get_cover_image(
        og_image_url=article.get("og_image_url"),
        image_query=cover_slide.get("image_query", ""),
    )
    logo_obj = get_company_logo(
        headline=cover_slide.get("headline", ""),
        category=cover_slide.get("category", ""),
    )

    # Stat slide image — Pexels search based on eyebrow + unit
    stat_slide = next((s for s in result["slides"] if s["type"] == "stat"), None)
    stat_image_obj = None
    if stat_slide:
        stat_query = f"{stat_slide.get('eyebrow', '')} {stat_slide.get('unit', '')}".strip()
        if stat_query:
            print("[writer] fetching stat image...", file=sys.stderr)
            stat_image_obj = fetch_pexels_image(stat_query)

    return {
        "slides": result["slides"],
        "caption": result["caption"],
        "og_image_url": article["og_image_url"],
        "image_obj": image_obj,
        "logo_obj": logo_obj,
        "stat_image_obj": stat_image_obj,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 watcher/writer.py <url>", file=sys.stderr)
        sys.exit(1)

    result = generate(sys.argv[1])
    out = {k: v for k, v in result.items() if k != "image_obj"}
    print(json.dumps(out, indent=2, ensure_ascii=False))
