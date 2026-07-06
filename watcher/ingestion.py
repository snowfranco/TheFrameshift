"""
Frameshift v2 — watcher/ingestion.py
Fetch, score, and rank article candidates for the auto-daily carousel flow.

Sources: Serper (all topics) + RSS (all feeds) + NewsAPI (top 3 topics),
         configured in config/sources.yaml.
Scoring: recency_weight × source_tier × signal_strength
Output:  top-10 ranked candidates sent to Telegram + saved to store/

Usage:
    python3 watcher/ingestion.py
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests
import yaml
from dotenv import load_dotenv

_ENV_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
)
load_dotenv(_ENV_PATH)

_SOURCES_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "sources.yaml")
)

_STORE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "store")
)

_CONFIG_CACHE = None


def _load_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        with open(_SOURCES_PATH) as fh:
            _CONFIG_CACHE = yaml.safe_load(fh)
    return _CONFIG_CACHE


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_published(val) -> str:
    """Convert feedparser struct_time or ISO string to UTC ISO string."""
    if val is None:
        return _now_utc().isoformat()
    if isinstance(val, str):
        return val
    try:
        import calendar
        ts = calendar.timegm(val)
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return _now_utc().isoformat()


def _parse_serper_date(val: str) -> str:
    """Parse Serper date strings, including relative formats like '3 hours ago'."""
    if not val:
        return _now_utc().isoformat()
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        pass
    v = val.lower()
    m = re.search(r"(\d+)\s+minute", v)
    if m:
        return (_now_utc() - timedelta(minutes=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\s+hour", v)
    if m:
        return (_now_utc() - timedelta(hours=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\s+day", v)
    if m:
        return (_now_utc() - timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\s+week", v)
    if m:
        return (_now_utc() - timedelta(weeks=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\s+month", v)
    if m:
        return (_now_utc() - timedelta(days=int(m.group(1)) * 30)).isoformat()
    # "Jun 10, 2026" or "June 10, 2026"
    month_day_year = re.search(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", val)
    if month_day_year:
        try:
            parsed = datetime.strptime(
                f"{month_day_year.group(1)} {month_day_year.group(2)} {month_day_year.group(3)}",
                "%b %d %Y",
            ).replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        except ValueError:
            try:
                parsed = datetime.strptime(
                    f"{month_day_year.group(1)} {month_day_year.group(2)} {month_day_year.group(3)}",
                    "%B %d %Y",
                ).replace(tzinfo=timezone.utc)
                return parsed.isoformat()
            except ValueError:
                pass
    # "10 Jun 2026" or "10 June 2026"
    day_month_year = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", val)
    if day_month_year:
        try:
            parsed = datetime.strptime(
                f"{day_month_year.group(1)} {day_month_year.group(2)} {day_month_year.group(3)}",
                "%d %b %Y",
            ).replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        except ValueError:
            pass
    return _now_utc().isoformat()


def _is_relevant(title: str, summary: str, keywords: list) -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in keywords)


# ── Fetchers ──────────────────────────────────────────────────────────────────

def fetch_serper(query: str, tier: str) -> list:
    api_key = os.environ.get("SERPER_API_KEY", "").strip()
    if not api_key:
        print("[ingestion] SERPER_API_KEY not set, skipping")
        return []
    try:
        resp = requests.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": 10},
            timeout=10,
        )
        resp.raise_for_status()
        news_items = resp.json().get("news", [])
    except Exception as exc:
        print(f"[ingestion] Serper error ({query!r}): {exc}")
        return []

    keywords = _load_config().get("relevance_keywords", [])
    results = []
    for item in news_items:
        url = item.get("link", "")
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue
        if keywords and not _is_relevant(title, item.get("snippet", ""), keywords):
            continue
        results.append({
            "title": title,
            "url": url,
            "source": item.get("source", "Serper"),
            "published_at": _parse_serper_date(item.get("date", "")),
            "tier": tier,
            "raw_score": 0.0,
        })
    return results


def fetch_rss(feed_url: str, name: str, tier: str) -> list:
    try:
        parsed = feedparser.parse(feed_url)
    except Exception as exc:
        print(f"[ingestion] RSS error ({name}): {exc}")
        return []

    keywords = _load_config().get("relevance_keywords", [])
    results = []
    for entry in parsed.entries[:20]:
        url = entry.get("link", "")
        title = (entry.get("title") or "").strip()
        if not url or not title:
            continue
        summary = entry.get("summary", "") or entry.get("description", "") or ""
        if keywords and not _is_relevant(title, summary, keywords):
            continue
        if getattr(entry, "published_parsed", None):
            pub = _parse_published(entry.published_parsed)
        elif getattr(entry, "updated_parsed", None):
            pub = _parse_published(entry.updated_parsed)
        else:
            pub = _now_utc().isoformat()
        results.append({
            "title": title,
            "url": url,
            "source": name,
            "published_at": pub,
            "tier": tier,
            "raw_score": 0.0,
        })
    return results


def fetch_newsapi(topic: str, tier: str) -> list:
    api_key = os.environ.get("NEWS_API_KEY", "").strip()
    if not api_key:
        print("[ingestion] NEWS_API_KEY not set, skipping")
        return []
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": topic,
                "sortBy": "publishedAt",
                "pageSize": 10,
                "language": "en",
                "apiKey": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
    except Exception as exc:
        print(f"[ingestion] NewsAPI error ({topic!r}): {exc}")
        return []

    results = []
    for a in articles:
        url = a.get("url", "")
        title = (a.get("title") or "").strip()
        if not url or not title or url == "https://removed.com":
            continue
        source_name = (a.get("source") or {}).get("name", "NewsAPI")
        results.append({
            "title": title,
            "url": url,
            "source": source_name,
            "published_at": a.get("publishedAt") or _now_utc().isoformat(),
            "tier": tier,
            "raw_score": 0.0,
        })
    return results


# ── Scoring ───────────────────────────────────────────────────────────────────

def score(item: dict) -> float:
    config = _load_config()
    scoring_cfg = config.get("scoring", {})
    halflife = scoring_cfg.get("recency_halflife_hours", 24)
    tier_map = config.get("source_tiers", {"A": 8, "B": 6, "C": 4, "D": 2})
    keywords = [k.lower() for k in scoring_cfg.get("signal_boost_keywords", [])]

    # recency_weight: exponential decay, 0.5 ** (hours_since / halflife)
    try:
        dt = datetime.fromisoformat(item.get("published_at", ""))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours_since = max(0.0, (_now_utc() - dt).total_seconds() / 3600)
    except Exception:
        hours_since = halflife  # treat unknown age as one half-life

    recency_weight = 0.5 ** (hours_since / halflife)

    # source_tier from sources.yaml source_tiers map
    source_tier = tier_map.get(item.get("tier", "C"), 4)

    # signal_strength: 1.0 base + 0.1 per keyword found in title, max 1.5
    title_lower = item.get("title", "").lower()
    signal_strength = 1.0
    for kw in keywords:
        if kw in title_lower:
            signal_strength = min(1.5, signal_strength + 0.1)

    result = round(recency_weight * source_tier * signal_strength, 4)
    item["raw_score"] = result
    return result


# ── Deduplication ─────────────────────────────────────────────────────────────

def _title_prefix(title: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", "", title.lower()).split()
    return " ".join(words[:8])


def _story_fingerprint(title: str) -> str:
    """Extract key nouns for story-level dedup across different sources."""
    stopwords = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "up", "about", "into", "is",
        "are", "was", "were", "has", "have", "had", "its", "it", "that",
        "this", "as", "be", "been", "will", "would", "could", "should",
        "may", "might", "can", "just", "also", "now", "new", "latest",
    }
    words = re.findall(r"[a-z]+", title.lower())
    key_words = sorted(w for w in words if w not in stopwords and len(w) > 3)
    return " ".join(key_words[:6])


def _url_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return url


def deduplicate(items: list) -> list:
    """Remove URL-level duplicates, then story-level semantic duplicates.
    When duplicates exist, the higher-scored item wins."""
    sorted_items = sorted(items, key=lambda x: x.get("raw_score", 0), reverse=True)
    seen_urls: set = set()
    seen_keys: set = set()
    kept = []
    for item in sorted_items:
        url = item.get("url", "")
        if url in seen_urls:
            continue
        key = (_url_domain(url), _title_prefix(item.get("title", "")))
        if key in seen_keys:
            continue
        seen_urls.add(url)
        seen_keys.add(key)
        kept.append(item)

    # Second pass: story-level semantic dedup.
    # If two items share 4+ of their 6 fingerprint words, keep higher score.
    seen_fingerprints = []
    story_deduped = []
    for item in kept:  # kept is already sorted by score descending
        fp = _story_fingerprint(item["title"]).split()
        is_duplicate = False
        for seen_fp in seen_fingerprints:
            seen_words = set(seen_fp)
            overlap = sum(1 for w in fp if w in seen_words)
            if overlap >= 4:
                is_duplicate = True
                break
        if not is_duplicate:
            story_deduped.append(item)
            seen_fingerprints.append(fp)

    return story_deduped


# ── Source diversity cap ──────────────────────────────────────────────────────

def _apply_source_cap(items: list, max_per_source: int = 3) -> list:
    """Keep at most max_per_source items per source. Items must be pre-sorted
    by score descending so the highest-scored survive the cap."""
    counts: dict = {}
    kept = []
    for item in items:
        src = item.get("source", "")
        if counts.get(src, 0) < max_per_source:
            kept.append(item)
            counts[src] = counts.get(src, 0) + 1
    return kept


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run() -> list:
    print("[ingestion] loading sources.yaml")
    config = _load_config()
    topics = config.get("topics", [])
    rss_feeds = config.get("rss_feeds", [])

    all_items = []

    # Serper — all topics
    print("[ingestion] fetching serper...")
    for t in topics:
        items = fetch_serper(t["query"], t["tier"])
        print(f"[ingestion]   serper {t['query']!r}: {len(items)} items")
        all_items.extend(items)

    # RSS — all feeds
    print("[ingestion] fetching rss...")
    for feed in rss_feeds:
        items = fetch_rss(feed["url"], feed["name"], feed["tier"])
        print(f"[ingestion]   rss {feed['name']}: {len(items)} items")
        all_items.extend(items)

    # NewsAPI — top 3 topics
    print("[ingestion] fetching newsapi...")
    for t in topics[:3]:
        items = fetch_newsapi(t["query"], t["tier"])
        print(f"[ingestion]   newsapi {t['query']!r}: {len(items)} items")
        all_items.extend(items)

    # Domain blocklist pre-filter
    blocklist = set(config.get("blocklist_domains", []))
    if blocklist:
        before = len(all_items)
        all_items = [i for i in all_items if _url_domain(i["url"]) not in blocklist]
        blocked = before - len(all_items)
        if blocked:
            print(f"[ingestion] blocklist filtered {blocked} items")

    # Hard recency cutoff — drop anything older than max_age_hours
    max_age_hours = config.get("scoring", {}).get("max_age_hours", 48)
    cutoff = _now_utc() - timedelta(hours=max_age_hours)
    def _within_cutoff(item: dict) -> bool:
        try:
            dt = datetime.fromisoformat(item["published_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt >= cutoff
        except Exception:
            return True  # unparseable → benefit of the doubt
    all_items = [i for i in all_items if _within_cutoff(i)]
    print(f"[ingestion] {len(all_items)} items after {max_age_hours}h recency filter")

    # Score all items
    for item in all_items:
        score(item)

    # Deduplicate (keeps highest-scored duplicate)
    deduped = deduplicate(all_items)

    # Sort by raw_score descending, apply source diversity cap, take top 10
    deduped.sort(key=lambda x: x.get("raw_score", 0), reverse=True)
    capped = _apply_source_cap(deduped, max_per_source=3)
    print(f"[ingestion] {len(capped)} candidates after dedup and diversity cap")
    top10 = capped[:10]

    # Format Telegram message
    lines = ["📋 Today's candidates — reply with story numbers to approve\n"]
    for i, item in enumerate(top10, 1):
        lines.append(f"{i}. [{item['raw_score']:.1f}] {item['title']} — {item['source']}")
    message = "\n".join(lines)

    # Send to Telegram
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if bot_token and chat_id:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=10,
            )
            resp.raise_for_status()
            print("[ingestion] candidate list sent to Telegram")
        except Exception as exc:
            print(f"[ingestion] Telegram send error: {exc}")
    else:
        print("[ingestion] Telegram not configured — printing candidate list")
        print(message)

    # Save full candidate list to store/
    os.makedirs(_STORE_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(_STORE_DIR, f"candidates_{ts}.json")
    with open(out_path, "w") as fh:
        json.dump(top10, fh, indent=2, ensure_ascii=False)
    print(f"[ingestion] saved {len(top10)} candidates → {out_path}")

    # Always write pending state so the bot can accept a selection
    pending_path = os.path.join(_STORE_DIR, "pending_candidates.json")
    with open(pending_path, "w") as fh:
        json.dump(
            {"timestamp": datetime.now(timezone.utc).isoformat(), "candidates": top10},
            fh, indent=2, ensure_ascii=False,
        )
    print(f"[ingestion] pending state written → {pending_path}")

    return top10


if __name__ == "__main__":
    candidates = run()
    print(json.dumps(candidates, indent=2, ensure_ascii=False))
