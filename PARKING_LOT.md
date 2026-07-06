# Frameshift v2 — Parking Lot

*Parked features, deferred ideas, and open questions. Nothing here is lost — 
everything has enough context to be picked up later.*

---

## Format

Each entry:
**[DATE] TITLE**
- What: one sentence
- Why parked: one sentence  
- Context: any relevant detail
- Triggers: what would make this worth picking up

---

## Parked

**[2026-06-12] Priority company logo PNGs for assets/logos/**
- What: Download transparent-background PNG logos for top 10 companies
  and place in assets/logos/{company}.png
- Priority companies: anthropic, openai, meta, google, nvidia, snap,
  spacex, microsoft, apple, samsung
- Why parked: Manual download task, not code
- Context: logo_fetcher.py local fallback already implemented.
  Google S2 shows white background box — local PNGs fix this cleanly.
- Source: company brand/press kits or SVG → PNG conversion
- Triggers: Any time a white-box logo appears on a carousel

**[2026-06-11] Open-source news ranking integration**
- What: Replace or augment custom scoring formula with an existing open-source 
  signal ranking solution (e.g. LunarCrush, NewsCatcher, GDELT)
- Why parked: Custom formula sufficient for v1 of ingestion; no existing solution
  purpose-built for AI + spatial computing signal quality
- Context: LunarCrush already connected as MCP in Claude. GDELT is heavy. 
  NewsCatcher is closest but adds API dependency. Could also be a standalone 
  open-source project.
- Triggers: custom scoring produces consistently poor candidates after 30+ days 
  of feedback data; or separate project opportunity is pursued

**[2026-06-11] Signal scoring as a standalone open-source library**
- What: A lightweight signal scoring library tuned for emerging tech topics — 
  does not exist yet as an open-source project
- Why parked: Out of scope for v2 build; noted as genuine gap in the ecosystem
- Context: Custom scorer.py in this project is the seed. If it works well after 
  30+ days, extraction as a library is viable.
- Triggers: scorer.py proves reliable; Snow decides to build in public

**[2026-06-11] Body image scraping for content slides**
- What: Extend scraper to collect body images from article, make available to
  context, stat, and signal slide renderers
- Why parked: Rendering fixes take priority; body image scraping adds complexity
  (filtering ads/icons/avatars) and should be a clean separate task
- Context: scrape() already returns og_image_url (hero image only). renderer.py
  already accepts image_obj on cover and context slides. Need to: (1) add body
  img tag scraping with 600x400px minimum filter to scraper.py, (2) add
  image_obj param to render_stat and render_signal, (3) pass body images through
  generate() and bot.py
- Triggers: rendering is stable and approved; body image quality from target
  article sources is validated

**[2026-06-11] Stat slide whitespace when content is short**
- What: Stat slide has excessive empty canvas when number + context is short
  (e.g. 2-line context leaves bottom 40% of slide blank)
- Why parked: Needs a design decision, not just a code fix; body image scraping
  may resolve it by filling space with a visual element
- Context: Three candidate solutions — (1) minimum content requirements enforced
  in writer.py before stat slide is used (e.g. context must be 3+ lines), (2)
  scale up number or context font further to fill space, (3) add a supporting
  visual element (body image or decorative rule) in the lower zone. Layout
  currently top-anchors at y=165 with bottom accent bar always pinned.
- Triggers: body image scraping is done (visual fill option becomes viable);
  or enough real articles sampled to know whether short context is the common case

**[2026-06-11] Meta Content Publishing API for direct Instagram posting**
- What: Replace manual Telegram delivery with direct Instagram carousel posting 
  via Meta API
- Why parked: Adds OAuth complexity; manual posting is acceptable for now
- Context: carousel_agent.py was the integration point in v1. Same applies here.
- Triggers: manual posting becomes the bottleneck; volume increases

---

## Closed
*Nothing closed yet.*
