# Frameshift v2 — Context Bootstrap

*Read this first. Under 60 lines.*

## Project
Frameshift v2 is a two-mode Instagram carousel generation system running on a MacBook. It converts any article URL into a branded 4–8 slide carousel (1080×1350px) delivered via Telegram. On-demand: send `/carousel <url>`, get slides in ~5 min. Auto-daily: scheduled ingestion, human approval, batch generation. Brand: The Frameshift (@ai.xr.frameshift). Built by Snow Abad.

## Current Phase
**All phases shipped and hardened.** 1A–5L complete; 2D cancelled. System is live. Bot runs as LaunchAgent. Next: CIA Phase 0 gate verification — confirm ~/shared/ context bus is readable by cold agent session, then begin CIA Phase 1 (ingest.py). Phase 2C (functional tests) deferred until real failure modes observed. See `ROADMAP.md` for full detail.

## Key Files

| File | Purpose |
|------|---------|
| `watcher/design_constants.py` | Source of truth: colours, type sizes, `WRITER_SCHEMA`, `WRITER_PROMPT` |
| `watcher/renderer.py` | Pillow PNG renderer — 8 slide types. Stable, do not touch. |
| `watcher/writer.py` | `scrape()` + `write()` + `generate()`; Groq llama-3.3-70b-versatile, 7-strategy scrape fallback + Jina |
| `watcher/image_fetcher.py` | OG image fetch + FLUX.1-schnell fallback; rotates 3 HF keys on 429 |
| `watcher/bot.py` | Telegram bot — on-demand `/carousel` + auto-daily scheduler (APScheduler, 08:00 Toronto) |
| `watcher/delivery.py` | Telegram media group sender ✅ |
| `watcher/ingestion.py` | Source scoring + candidate selection ✅ — Serper + RSS + NewsAPI, top-10 to Telegram |
| `watcher/feedback.py` | Scrape reliability tracking — logs attempts, updates `domain_reliability` in scoring_weights.json |
| `watcher/scorer.py` | Domain reliability scoring — `load_weights()`, `save_weights()`, `score()` |
| `config/sources.yaml` | Topics, RSS feeds, source tiers, scoring config, relevance keywords, blocklist |
| `.env` | API keys: GROQ_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, HF_API_KEY(s), SERPER_API_KEY, NEWS_API_KEY |
| `ROADMAP.md` | Phase status, build sequence, decisions log |
| `DECISIONS.md` | Architecture decision records — why not what |
| `RUNLOG.md` | Operational history — notable runs, failures, fixes |
| `docs/` | Agent-first HTML: index.html, architecture.html, roadmap.html, context.md |

## Active Rules
- **Ground or abstain**: if source doesn't support a claim, omit the slide — wired into prompt, not code
- **Read before write, diff before save** on every file touched
- **Clean seams**: one input type, one output type per module; testable in isolation
- **Docs and tests ship with each phase**, never deferred
- **Daily context update** after anything ships: update `ROADMAP.md` first, then affected docs
- **Before any renderer change**: run `make regression` (pixel-diff baselines); **before any deploy**: run `python3 tests/smoke.py` (full pipeline, 9 checks)

## Known Issues
- Bot runs as LaunchAgent — restart after code changes: `launchctl unload ~/Library/LaunchAgents/com.frameshift.bot.plist && launchctl load ~/Library/LaunchAgents/com.frameshift.bot.plist`
- Logo white-box issue: Google S2 returns favicons with background — local PNGs needed in `assets/logos/` for priority companies (see PARKING_LOT.md)
- Stat slide has excess whitespace on short content — parked pending body image scraping (see PARKING_LOT.md)
- feedback.py and scorer.py have real logic — need 30+ days of data before domain reliability multiplier has meaningful scoring effect
- Curly quote risk: Claude Code may insert Unicode smart quotes into Python literals — run `grep -P '[''""]' watcher/renderer.py` after any renderer edits
- 2C functional tests deferred — write after real failure modes are observed in production
- claude.ai sessions: do not attempt filesystem commands — all context comes from the pasted bootstrap, not disk

## Do Not Touch
- `watcher/renderer.py` — stable, approved
- `watcher/design_constants.py` — stable, approved
- `fonts/` directory
