# Frameshift v2 — Run Log
*Notable operational events, first-runs, failures, and fixes.*
*Add new entries at the top. Date format: YYYY-MM-DD.*

---

## 2026-06-13 — Ingestion fixes + system hardening
- Serper date parser fixed — "Jun 10, 2026", "1 week ago", "2 months ago" formats now handled
- Story semantic dedup added — 4-word fingerprint overlap threshold eliminates same story from multiple sources
- arXiv RSS URL corrected to rss.arxiv.org (old arxiv.org/rss 302-redirected; feedparser returned 0 items)
- Bot now runs as LaunchAgent — survives Mac sleep/reboot (com.frameshift.bot.plist, KeepAlive=true)
- Logo feature shipped — 28 companies, Google S2 favicon / local assets/logos/ fallback
- Pexels image fallback wired (OG → Pexels → FLUX → placeholder)
- Source fallback on 403 — Serper searches alternative coverage on TC/Verge/Wired/Ars
- ~/shared/ ecosystem context bus created — master-context.md, CIA/CCA scaffolded
- ~/oneninefour/ standards: agent-patterns.md + PARKING_LOT.md

## 2026-06-13 — No candidates surfaced
- Daily 8am run completed but returned 0 stories above threshold
- No carousels generated or delivered today

## 2026-06-12 — Logo feature shipped
- Company logos now appear above headline on cover slides
- Detection: 28 companies in COMPANY_DOMAINS dict
- Source: Google S2 favicon API → local assets/logos/ fallback
- Known issue: S2 returns white-background favicons — local PNGs
  needed for priority companies (Anthropic, OpenAI, Meta, etc.)
- assets/logos/ directory created — add transparent PNGs manually

## 2026-06-12 — First automated daily run
- Bot running at 8am Toronto schedule
- Candidates surfaced: 10 stories
- Missing cover images on 3 articles (CNBC, technology.org)
- Pexels fallback wired to fix this going forward
- 403 on techxplore.com — Serper alternative search now handles
- Groq 400 on one story — body sanitization fix applied

## 2026-06-12 — Pexels + source fallback shipped
- Image chain: OG → Pexels → FLUX → placeholder
- FLUX keys were empty since project start — silently broken
- Pexels key added, confirmed working (portrait orientation)
- Source fallback: on 403, Serper searches for alternative coverage
  on TC/Verge/Wired/Ars before sending user-facing error

## 2026-06-11 — Full system shipped
- All phases 0–4 complete
- On-demand: /carousel <url> → slides in ~2 min
- Auto-daily: 8am scheduler → candidate list → approval → delivery
- Smoke test: 9/9 checks passing
- Regression baselines: 18/18 locked
- Docs: 6 HTML files, fully cross-linked, agent-navigable

## 2026-06-11 — First successful end-to-end carousel
- Article: Snap acquires AR firm Illumix (Variety)
- URL: variety.com/2026/digital/tech/snap-acquires-illumix-...
- Slides: cover (Evan Spiegel OG image) → stat → quote → signal → cta
- Caption: 74 words, led with acquisition + smartglasses transition
- Delivered: 5 PNGs to Telegram @ai.xr.frameshift
- Reference: This is the benchmark for "what good looks like"

## 2026-06-11 — LLM switched from Gemini to Groq
- Gemini: free tier quota exhausted, org policy blocked billing
- Groq llama-3.1-8b-instant: failed schema compliance entirely
- Groq llama-3.3-70b-versatile: correct field names, good output
- Schema enforcement prompt (_SCHEMA_ENFORCEMENT) required even
  with 70B model — model ignores abstract schema without it

## 2026-06-11 — Known bad domains identified
- inc.com: hard paywall, 403 on all attempts, Jina also fails
- fastcompany.com: same
- techxplore.com: 403 but Jina fallback recovers it
- Action: inc.com + fastcompany.com added to blocklist_domains
