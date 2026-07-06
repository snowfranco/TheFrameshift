# Frameshift v2 — Carousel System Roadmap

*Last updated: 2026-06-13 — 1A–1H, 2A, 2B, 3A–3F, 4A–4B, 5A–5L shipped*

---

## What This Is

A lean, two-mode carousel generation system running on a MacBook. Send a URL to
Telegram and get a branded Instagram carousel back in under 10 minutes. Or let
it run on a schedule, approve a source list, and receive 3-5 carousels daily.
No vector store, no dashboard, no ChromaDB. Flat files and clean module seams.

Built by Snow Abad. Brand: The Frameshift (@ai.xr.frameshift).

---

## Status Board

| Phase | What | Status | Shipped |
|-------|------|--------|---------|
| 0A | Design system — 8 slide types approved, pixel spec locked | ✅ shipped | 2026-06-11 |
| 0B | renderer.py — all 8 slide types, Pillow PNG, 1080×1350 | ✅ shipped | 2026-06-11 |
| 0C | design_constants.py — pixel spec, writer schema, prompt template | ✅ shipped | 2026-06-11 |
| 0D | writer.py — scrape + Groq → validated slide JSON | ✅ shipped | 2026-06-11 |
| 0E | Real fonts installed — EB Garamond + DM Sans | ✅ shipped | 2026-06-11 |
| 1A | delivery.py — Telegram media group sender | ✅ shipped | 2026-06-11 |
| 1B | On-demand flow — /carousel <url> bot command end-to-end | ✅ shipped | 2026-06-11 |
| 1C | Unit tests — test_renderer.py + test_writer_schema.py | ✅ shipped | 2026-06-11 |
| 1D | docs/architecture.html — stack, module map, data flow | ✅ shipped | 2026-06-11 |
| 1E | docs/roadmap.html — generated from ROADMAP.md | ✅ shipped | 2026-06-11 |
| 1F | docs/index.html — project overview, RL/CMS reference | ✅ shipped | 2026-06-11 |
| 1G | docs/context.md — 39-line agent context bootstrap | ✅ shipped | 2026-06-11 |
| 1H | PARKING_LOT.md — created, 3 parked entries | ✅ shipped | 2026-06-11 |
| 2A | ingestion.py — Serper + RSS + News API source scoring | ✅ shipped | 2026-06-11 |
| 2B | Auto-daily flow — schedule + approval + batch delivery | ✅ shipped | 2026-06-11 |
| 2C | Functional tests — test_full_pipeline.py + test_ground_or_abstain.py | 💡 planned | — |
| 2D | docs/pipeline.html | ❌ cancelled | — |
| 3A | OG image scrape + FLUX fallback wired into renderer | ✅ shipped | 2026-06-11 |
| 3B | Cover slide with real images end-to-end | ✅ shipped | 2026-06-11 |
| 3E | Scraper robustness — 7-strategy fallback chain + Jina Reader API | ✅ shipped | 2026-06-11 |
| 3F | Self-learning scrape reliability — feedback.py + scorer.py | ✅ shipped | 2026-06-11 |
| 3C | Regression baselines locked (tests/regression/) | ✅ shipped | 2026-06-11 |
| 3D | docs/design-system.html + docs/writer-contract.html | ✅ shipped | 2026-06-11 |
| 4A | Hardening — smoke test (tests/smoke.py) | ✅ shipped | 2026-06-11 |
| 4B | docs/runbook.html | ✅ shipped | 2026-06-11 |
| 5A | Logo feature — company logos on cover slides via logo_fetcher.py | ✅ shipped | 2026-06-13 |
| 5B | Pexels image fallback — OG → Pexels → FLUX → placeholder | ✅ shipped | 2026-06-13 |
| 5C | Source fallback on 403 — Serper searches alternative coverage before failing | ✅ shipped | 2026-06-13 |
| 5D | Body sanitization — prevents Groq 400 errors on malformed scraped content | ✅ shipped | 2026-06-13 |
| 5E | Serper date parser — "Jun 10, 2026" / "1 week ago" / "2 months ago" formats handled | ✅ shipped | 2026-06-13 |
| 5F | Story-level semantic dedup — fingerprint overlap prevents same story flooding top slots | ✅ shipped | 2026-06-13 |
| 5G | LaunchAgent — bot persists across Mac sleep/reboot (com.frameshift.bot.plist) | ✅ shipped | 2026-06-13 |
| 5H | arXiv RSS URL fixed — rss.arxiv.org (old URL 302-redirected, feedparser returned 0 items) | ✅ shipped | 2026-06-13 |
| 5I | DECISIONS.md — 12 ADRs, architecture decisions documented | ✅ shipped | 2026-06-13 |
| 5J | RUNLOG.md — operational history from day one | ✅ shipped | 2026-06-13 |
| 5K | ~/shared/ ecosystem context bus — master-context, CIA/CCA scaffolded | ✅ shipped | 2026-06-13 |
| 5L | ~/oneninefour/ standards — agent-patterns.md + PARKING_LOT.md | ✅ shipped | 2026-06-13 |

---

## Phase Detail

### Phase 0 — Foundation ✅

**What was built**: Full slide palette designed as React artifact, approved by
Snow. Cover template matched to existing brand sample. 8 slide types defined:
cover (fixed), stat, quote, context, contrast, timeline, explainer, signal, cta
(fixed). Lavender `#b8a9d9` accent, warm off-white `#f7f4ef` content slides,
pure black `#000000` CTA.

**Key decisions**:
- Slide structure is instruction-driven, not hardcoded — LLM selects from
  palette based on story, 2-6 middle slides, ground-or-abstain enforced
- Cover headline dynamically sized 96px→54px to fill bottom third of slide
- Stat slide content top-anchored, accent bar pinned to bottom
- Images only on cover (full-bleed) and context slides (optional zone)

---

### Phase 0B — renderer.py ✅

**Built**: `watcher/renderer.py` — renders all 8 slide types to 1080×1350 PNG.

**Key decisions**:
- Font fallback: checks `fonts/` for EB Garamond + DM Sans, falls back to
  DejaVu if missing or under 1KB — pipeline never dies on missing fonts
- Slide dispatch via `RENDERERS` dict — adding a new slide type is one function
  + one dict entry, nothing else changes
- `render_carousel(slides_json)` is the single public interface
- Test fixture (TEST_CAROUSEL) embedded in `__main__` — run standalone to
  verify any slide type

**Fonts**: EB Garamond (Regular, Italic, Bold) + DM Sans (Regular, Medium, Bold)
installed at `~/frameshift_v2/fonts/` on 2026-06-11.

---

### Phase 0C — design_constants.py ✅

**Built**: `watcher/design_constants.py` — single source of truth for all design
values, writer schema, and prompt template.

**Key decisions**:
- All pixel values at 1080×1350 (3x scale from 360×450 mockup)
- WRITER_SCHEMA defines exact JSON fields + word limits per slide type
- WRITER_PROMPT is the palette instruction — slide selection logic lives here,
  not in code. Change the prompt, change the behaviour.
- `{article_text}` placeholder uses `.replace()` not `.format()` to avoid
  double-brace escaping issues with JSON examples in the template

---

### Phase 0D — writer.py ✅

**Built**: `watcher/writer.py` — scrape + LLM → validated slide JSON. (LLM was originally Gemini; switched to Groq llama-3.1-8b-instant at 0D, then upgraded to llama-3.3-70b-versatile in Phase 1 for schema compliance — see Phase 1 Key Decisions.)

**Key decisions**:
- LLM switched to Groq llama-3.1-8b-instant — GROQ_API_KEY from v1. Upgraded to llama-3.3-70b-versatile in Phase 1.
- `scrape()`: requests + BeautifulSoup, OG title/image/body extraction,
  raises ValueError if body < 200 chars
- `write()`: Groq llama-3.1-8b-instant, temperature=0.3, max_tokens=2000,
  single call with 429 backoff (parses retry-after from response)
- Validation: first slide must be cover, last must be cta, 2-6 middle slides,
  all types must exist in RENDERERS.keys()
- NEWS_API_KEY loaded at module level for use by ingestion.py later
- .env loaded relative to `__file__`, not cwd — works from any invocation path
- sys.path patched so imports work from project root or watcher/ directly

---

### Phase 1 — On-demand flow ✅

**Built**: Full end-to-end on-demand carousel delivery via Telegram.

**1A — delivery.py**: Send rendered PNGs + caption to Telegram as a media group.
- Read slide PNGs from output dir
- Send via python-telegram-bot as `send_media_group`
- Confirm delivery, log to `store/delivered.json`

**1B — On-demand bot**: Telegram bot listens for `/carousel <url>` command.
- Validate URL
- Call `writer.generate(url)` → `renderer.render_carousel(slides)` → `delivery.send()`
- Reply with slides in ~5 min
- Error handling: scrape fail → reply with reason; generation error → retry once

**Key decisions**:
- LLM switched from Gemini to Groq `llama-3.3-70b-versatile` — `llama-3.1-8b-instant` failed schema compliance (generated wrong field names)
- Schema enforcement: field names injected at call time in `writer.py` via `_SCHEMA_ENFORCEMENT` block — `design_constants.py` untouched
- Caption: generated by LLM as top-level field (3-4 sentences, max 60 words, third person, no brand mention) — not pulled from CTA headline
- Caption format: `{caption}\n\n{source_url}` attached to first slide only (Telegram media group behaviour)
- `stat.number` and `signal.tag` exempt from 3-char minimum validation (can be `"3"` or `"AI"`)
- `writer.py` prints redirected to stderr so `> file.json` captures clean JSON stdout

**1C — Unit tests** (`tests/unit/`):
- `test_renderer.py` — each slide type renders, output is 1080×1350, spot color checks
- `test_writer_schema.py` — validator rejects bad JSON, accepts valid

**1D — docs/architecture.html**:
- Stack overview, module map, file paths, API keys used, data flow diagram

**1E — docs/roadmap.html**:
- Generated from ROADMAP.md, kept in sync

**1F — docs/index.html** ✅:
- Project overview: what-is-this, multi-agent architecture, self-learning/RLHF, scoring formula, context management system, daily context update protocol

**1G — docs/context.md** ✅:
- 39-line agent context bootstrap; orients any agent in one read; pinned in Claude Project

**1H — PARKING_LOT.md** ✅:
- Created with 3 parked entries: open-source news ranking, signal scoring lib, Meta Content Publishing API

---

### Phase 2 — Auto-daily flow ✅ (2A/2B shipped — 2C planned — 2D cancelled)

**2A — ingestion.py** ✅: Source scoring for auto-daily flow.
- Fetch: Serper (all topics) + RSS (8 feeds) + NewsAPI (top 3 topics)
- Score: recency_weight × source_tier × signal_strength
- Output: ranked top-10 candidate list → Telegram + `store/candidates_{ts}.json`

**Key decisions**:
- Three sources: Serper (topic queries) + RSS (8 feeds incl. OpenAI Blog, Google AI Blog, HuggingFace, arXiv) + NewsAPI
- Scoring formula: `recency_weight × source_tier × signal_strength`
  - recency: `0.5 ** (hours_since / 24)`, hard cutoff at 48h before scoring
  - source_tier: A=8, B=6, C=4, D=2 from `sources.yaml`; arXiv upgraded D→C
  - signal_strength: 1.0 base + 0.1 per keyword match in title, max 1.5
- Source diversity cap: max 3 items per source before top-10 slice
- Keyword relevance filter on title + summary/snippet applied per fetcher
- Domain blocklist: stocktwits.com, reddit.com, twitter.com, x.com, bluesky
- Serper relative dates ("3 hours ago") parsed to ISO; unparseable → now() not halflife
- Hard recency cutoff: items older than 48h dropped; unparseable dates kept (benefit of the doubt)
- `scorer.py` stub created: `load_weights()`, `save_weights()`, `adjust()`
- Google AI Blog URL corrected to `blog.google/technology/ai/rss/`

**2B — Auto-daily flow** ✅: Scheduled ingestion, Telegram approval, batch delivery.
- Run ingestion, send candidate list to Telegram
- Wait for approval reply (Go/Kill per story, or approve all)
- Generate + deliver approved carousels
- Log run to store/run_log.json

**Key decisions**:
- bot.py: single entry point for both on-demand and auto-daily flows
- APScheduler AsyncIOScheduler: daily run at 08:00 America/Toronto
- Approval loop: ALL / 1,3,5 / SKIP pattern parsed from Telegram reply
- 2-hour timeout on approval — skips run if no reply
- State: store/pending_candidates.json written after ingestion, deleted after approval processed
- Blocking isolation: writer/renderer/delivery run via asyncio.to_thread()
- Run log: store/run_log.json, one entry per carousel
- Owner-only /run command for manual trigger

**2C — Functional tests** (`tests/functional/`):
- `test_full_pipeline.py` — URL → JSON → PNGs, mocked Groq response
- `test_ground_or_abstain.py` — thin article → max 2 middle slides

**2D — docs/pipeline.html**: ❌ Cancelled. Superseded by `architecture.html#pipeline-diagrams` (flow diagrams) and `runbook.html#daily-flow` (operational flows). No separate file needed.

---

### Phase 3 — Images + Robustness ✅ (3A, 3B, 3E, 3F shipped — 3C, 3D planned)

**3A — image_fetcher.py** ✅: OG image scrape + FLUX fallback.
- `fetch_og_image(url)` — GET OG image, validate ≥400×300px, convert RGB
- `fetch_flux_image(prompt)` — FLUX.1-schnell via HuggingFace router, rotates 3 HF keys on 429
- `get_cover_image(og_image_url, image_query)` — OG first, FLUX fallback, None if both fail

**3B — Cover slide with real images** ✅: Full end-to-end with real article images.
- `writer.generate()` now returns `image_obj` (PIL Image) alongside slides JSON
- `render_carousel()` passes `image_obj` to both cover and context renderers
- `bot.py` passes `image_obj` through the generation → render pipeline

**Key decisions**:
- OG image minimum size: 400×300px — smaller images rejected, FLUX used instead
- All print statements in `image_fetcher.py` use `stderr` to keep stdout clean for JSON piping
- Telegram media group hard cap: 10 slides max, truncates with warning if exceeded
- Quote slide: text now 96px italic serif, fills ~3/4 of slide
- Signal slide: headline 126px, implication 45px, fills ~3/4 of slide
- Stat slide whitespace issue parked — body image scraping needed first (see PARKING_LOT.md)
- Curly quote bug: Claude Code inserted smart quotes in Python — fixed by byte-replacing all non-ASCII quotes with ASCII equivalents
- `render_carousel()` passes `image_obj` to both cover and context slides

**3E — Scraper robustness** ✅: 7-strategy fallback chain + Jina Reader API.
- Strategy chain in `scrape()`: `<p> tags → <article> → content divs → <main> → largest div → mobile UA → Jina Reader API`
- HTTP 403 responses skip HTML strategies and go directly to Jina
- `bot.py` updated with user-friendly scrape failure messaging

**Key decisions**:
- Jina Reader API (`r.jina.ai/{url}`) handles JS-rendered pages (Remix/Next.js SPAs) and 403 paywalls
- 403 responses: log `[scraper] HTTP {status} — trying Jina fallback` then skip all HTML parsing
- Mobile UA fallback uses iPhone UA — some sites serve lighter pages with full article text
- `_extract_body()` helper tries strategies in order, returns `(text, strategy_label)` for logging
- bot.py scrape failures send `⚠️ Couldn't fetch that article. Try archive.ph / 12ft.io.` — raw error hidden
- `_strip_raw_json()` removes `\n\nRaw:` tail from validation errors in user-facing Telegram messages
- `_FIELD_MIN` dict replaces `_SHORT_OK` set — enforces exact per-field minimums (category=2, number/tag/unit=1)
- Caption requirements added to `WRITER_PROMPT` in `design_constants.py` (not just `_SCHEMA_ENFORCEMENT`) — harder to regress

**3F — Scrape reliability** ✅: `feedback.py` + `scorer.py` domain reliability tracking.
- `record_scrape_attempt(url, success, reason)` logs to `store/feedback_log.json`
- `adjust_domain_reliability(domain, success)` updates `domain_reliability` in `store/scoring_weights.json`
- `scorer.score(item)` applies reliability multiplier to candidate scores after 3+ attempts

**Key decisions**:
- Reliability formula: `(attempts - failures) / attempts` — simple, interpretable
- Multiplier only applied after 3+ attempts — prevents premature demotion on sparse data
- Domains with reliability < 30% after 3+ attempts print blocklist warning to stderr
- `inc.com` and `fastcompany.com` added to `blocklist_domains` in `config/sources.yaml` immediately
- `scoring_weights.json` now contains `source_weights` / `topic_weights` (stubs) and `domain_reliability` (active)
- bot.py records success/failure on each carousel attempt; scrape errors record `success=False`
- Needs 30+ days of live data before reliability multiplier has meaningful scoring effect

**3C — Regression baselines** ✅ (`tests/regression/`):
- 9 baseline PNGs locked (one per slide type, 53–135 KB each) using real EB Garamond + DM Sans fonts
- `test_renderer_regression.py` — 18 tests: 9 dimension checks (1080×1350) + 9 zero-diff pixel checks
- `generate_baselines.py` — regenerates all 9 baselines from REGRESSION_CAROUSEL (TEST_CAROUSEL + explainer)
- `make regression` runs the suite; `make update-baselines` refreshes baselines after intentional design changes
- TEST_CAROUSEL in renderer.py lacks an explainer slide — REGRESSION_CAROUSEL adds it between timeline and signal

**3D — docs/design-system.html + docs/writer-contract.html** ✅:
- `design-system.html` — 18-colour swatch table, 20-row typography table, all 9 slide-type subsections with when-to-use / fields / word limits / layout notes, spacing constants table, update-baselines procedure
- `writer-contract.html` — Groq model config, full output schema (pre/code), per-slide field tables with req/opt badges, palette selection rules, validation rules, ground-or-abstain with correct/incorrect examples, caption requirements
- Top nav updated in all 5 docs: Design System and Writer Contract now live links (were ghosts)

---

### Phase 4 — Hardening ✅

**Plan**: Smoke test + runbook. Pipeline is production-stable.

**4A — Smoke test** ✅ (`tests/smoke.py`):
- One live URL, no mocks, 9 checks, full pipeline end-to-end
- Checks: scrape → write (Groq) → caption ≥50 words → slide structure → image type → render → PNG count → dimensions → Telegram delivery
- Pass/fail in < 3 min. Run with `make smoke` or `python3 tests/smoke.py [url]`
- Delivery inside tempdir context — PNGs exist for Telegram send, cleaned up after
- delivery.send() is synchronous (calls asyncio.run() internally) — not wrapped again

**4B — docs/runbook.html**:
- How to run, restart, debug, add a new slide type

---

### Phase 5 — Post-launch hardening ✅

**What was built**: Ingestion reliability, image quality, scraper robustness, bot process management, ecosystem scaffolding.

**5A — Logo feature** ✅: Company logos on cover slides.
- `watcher/logo_fetcher.py` — 28-company detection dict, Google S2 favicon API, local `assets/logos/` fallback
- `renderer.py` — logo paste above headline block on cover slide; 3× scaled, 85% opacity
- `writer.py` — `get_company_logo()` called in `generate()`, returned as `logo_obj`
- `bot.py` — all 4 `_render_carousel` call sites pass `logo_obj=logo_obj`

**5B — Pexels image fallback** ✅:
- Image chain: OG → Pexels → FLUX → dark placeholder
- `PEXELS_API_KEY` added to `.env`; portrait orientation filter gives carousel-ready images
- HF_API_KEY warning: logs `[image] HF_API_KEY not set — FLUX fallback disabled` if all keys empty

**5C — Source fallback on 403** ✅:
- `_serper_alternative(headline)` searches TC/Verge/Wired/Ars for alternative coverage
- On scrape failure, Serper finds alt URL → retries writer.generate() before sending user-facing error

**5D — Body sanitization** ✅:
- `scrape()` sanitizes body before Groq: null bytes → control chars → UTF-8 round-trip → truncate 6000 chars
- Fixes Groq 400 Bad Request on malformed content from aggressive scrapers

**Key decisions**:
- Serper dates were all falling back to now() — "Jun 10, 2026" / "1 week ago" / "2 months ago" formats not handled. Fixed with month-name parser + week/month relative branches.
- Story dedup was domain+title prefix only — same story from 3 different sources filled top 3 slots. Fixed with semantic fingerprint (6 sorted key words, 4-word overlap threshold).
- arXiv URL changed from arxiv.org/rss to rss.arxiv.org — feedparser doesn't follow 302 redirects, returned 0 items every run.
- Bot was not persisting — no LaunchAgent, died on terminal close or Mac sleep. Fixed with launchctl LaunchAgent (com.frameshift.bot.plist), KeepAlive=true. Scheduler now fires reliably at 8am Toronto.

---

## Key File Index

| File | Purpose |
|------|---------|
| watcher/design_constants.py | Pixel spec, colours, writer schema, prompt template |
| watcher/renderer.py | Pillow PNG renderer — 8 slide types |
| watcher/writer.py | scrape() + write() + generate() |
| watcher/image_fetcher.py | OG image fetch → Pexels → FLUX fallback; rotates HF keys on 429 |
| watcher/logo_fetcher.py | Company logo detection + fetch (Google S2 favicon / local PNG fallback) |
| watcher/ingestion.py | Serper + RSS + NewsAPI fetching, scoring, dedup, Telegram send ✅ |
| watcher/feedback.py | Scrape reliability tracking — record_scrape_attempt(), adjust_domain_reliability() |
| watcher/scorer.py | Domain reliability scoring — load_weights(), save_weights(), score() |
| watcher/bot.py | Telegram bot — on-demand /carousel + auto-daily scheduler |
| watcher/delivery.py | Telegram media group sender ✅ |
| config/sources.yaml | RSS feeds + search topics |
| fonts/ | EB Garamond + DM Sans TTF files |
| store/ | Flat JSON run logs, rendered output |
| .env | API keys |
| com.frameshift.bot.plist | LaunchAgent — bot process manager (install to ~/Library/LaunchAgents/) |
| ROADMAP.md | This file |
| DECISIONS.md | Architecture decision records — why not what |
| RUNLOG.md | Operational history — notable runs, failures, fixes |

---

## Architecture Principles

- **No database**: flat JSON files only. Stories live as JSON per run, deleted after delivery.
- **Clean seams**: each module has one input type, one output type. Testable in isolation.
- **Ground or abstain**: if source doesn't support a claim, omit the slide. Wired into prompt, not retrofitted.
- **Instruction-driven structure**: slide selection is a prompt, not code. Change behaviour by editing the prompt.
- **Fallback everywhere**: Groq model fallback (llama-3.1-70b-versatile on 429), font fallback, image fallback (OG → FLUX → dark placeholder). Pipeline never dies silently.
- **Documentation ships with each phase, not after**: tests/ and docs/ are built alongside features, never deferred.
