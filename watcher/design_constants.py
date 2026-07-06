"""
Frameshift Carousel — Design Constants
Extracted from approved React mockup v2.
All pixel values are for 1080x1350px output (3x scale from 360x450 mockup).
"""

# ── CANVAS ──────────────────────────────────────────────────────────────────
CANVAS_W = 1080
CANVAS_H = 1350
SCALE = 3  # mockup was 360x450

# ── COLOURS ─────────────────────────────────────────────────────────────────
BLACK       = "#000000"   # CTA background
NEAR_BLACK  = "#0d0d0d"   # cover overlay base, contrast cell A, body text
OFF_WHITE   = "#f7f4ef"   # all content slide backgrounds
WHITE       = "#ffffff"   # text on dark

ACCENT      = "#b8a9d9"   # lavender — cover rule+arrow, stat bar, quote line
ACCENT_DARK = "#7a6aaa"   # lavender dark — kickers, timeline dots, signal tag

# Cover overlay gradient (bottom-heavy)
COVER_GRADIENT = [
    (0.00, (0, 0, 0, 38)),    # 15% opacity
    (0.55, (0, 0, 0, 128)),   # 50% opacity
    (1.00, (0, 0, 0, 217)),   # 85% opacity
]

# Content slide divider / rule
RULE_COLOR  = "#e8e3da"

# Contrast cells
CONTRAST_A_BG     = "#0d0d0d"
CONTRAST_B_BG     = "#eee8e0"
CONTRAST_B_BORDER = "#ddd7cc"

# Signal tag
SIGNAL_TAG_BG     = "#ede8f5"
SIGNAL_TAG_BORDER = "#d0c4e8"

# Quote mark decorative colour
QUOTE_MARK_COLOR  = "#e8e0f0"

# Muted tones
MUTED_TEXT   = "#999999"   # units, attribution
BODY_TEXT    = "#555555"   # body copy
DARK_TEXT    = "#1a1a1a"   # quote text
LABEL_TEXT   = "#bbbbbb"   # eyebrows, kickers (non-accent)
WORDMARK_DIM = "#cccccc"   # small wordmark on content slides
SLIDE_NUM    = "#cccccc"

# ── TYPOGRAPHY ───────────────────────────────────────────────────────────────
# Font files must be present at these paths in the rendering env
FONT_SERIF        = "fonts/EBGaramond-Regular.ttf"
FONT_SERIF_ITALIC = "fonts/EBGaramond-Italic.ttf"
FONT_SERIF_BOLD   = "fonts/EBGaramond-Bold.ttf"
FONT_SANS         = "fonts/DMSans-Regular.ttf"
FONT_SANS_MEDIUM  = "fonts/DMSans-Medium.ttf"
FONT_SANS_BOLD    = "fonts/DMSans-Bold.ttf"

# Scale note: all sizes below are at 1080x1350 (3x)
class Type:
    # Cover
    COVER_WORDMARK   = 45   # DM Sans Bold
    COVER_HEADLINE   = 108  # EB Garamond Regular
    COVER_PILL       = 28   # DM Sans Medium, spaced caps
    # Content header
    HEADER_WORDMARK  = 33   # DM Sans Bold, muted
    HEADER_NUM       = 30   # DM Sans Medium, muted
    # Eyebrows / kickers
    EYEBROW          = 30   # DM Sans SemiBold, spaced caps, uppercase
    # Body type
    BODY             = 39   # DM Sans Regular
    BODY_SM          = 37   # DM Sans Regular (tight slides)
    # Serif display
    SERIF_DISPLAY    = 258  # EB Garamond — stat number
    SERIF_HEADLINE   = 78   # EB Garamond — context/signal/explainer headline
    SERIF_QUOTE      = 63   # EB Garamond Italic
    SERIF_QUOTE_MARK = 192  # EB Garamond decorative
    # Stat
    STAT_UNIT        = 36   # DM Sans Regular, muted
    # CTA
    CTA_HANDLE       = 33   # DM Sans Regular, spaced caps, muted
    CTA_HEADLINE     = 102  # EB Garamond Bold, centered
    # Signal tag / pill
    TAG              = 30   # DM Sans SemiBold, spaced caps

# ── SPACING & LAYOUT ─────────────────────────────────────────────────────────
PAD_H = 66        # horizontal padding (content slides)
PAD_V = 60        # top padding (content slides)
HEADER_H = 60     # height of header zone (wordmark + rule)
RULE_TOP_Y = 90   # y position of hairline rule under header
RULE_THICKNESS = 3

# Cover
COVER_WORDMARK_X = 66
COVER_WORDMARK_Y = 66
COVER_BOTTOM_PAD = 66  # padding from bottom edge
COVER_PILL_RADIUS = 30
COVER_RULE_Y_FROM_BOTTOM = 45  # rule sits 45px above bottom edge
COVER_RULE_ARROW_W = 24
COVER_RULE_ARROW_H = 15

# Stat slide
STAT_NUMBER_Y = 180   # y start of big number (below header)
STAT_ACCENT_H = 9     # bottom accent bar height

# Quote slide
QUOTE_LINE_X = 66
QUOTE_LINE_TOP = 204
QUOTE_LINE_BOTTOM_PAD = 150  # from bottom
QUOTE_LINE_W = 6
QUOTE_INNER_X = 108   # text starts after the line

# Timeline
TIMELINE_DOT_R = 12
TIMELINE_LINE_W = 3
TIMELINE_ITEM_GAP = 54

# CTA
CTA_RULE_W = 240
CTA_RULE_Y_FROM_CENTER = -120  # above center

# ── SLIDE TYPES ──────────────────────────────────────────────────────────────
SLIDE_TYPES = [
    "cover",      # fixed — always first
    "stat",       # single number reframes story
    "quote",      # direct quote > paraphrase
    "context",    # what happened + optional image
    "contrast",   # two competing things
    "timeline",   # sequence matters
    "explainer",  # reader needs context first
    "signal",     # forward-looking implication
]

# ── WRITER SCHEMA ─────────────────────────────────────────────────────────────
# Gemini must output this exact structure. Renderer reads nothing else.
WRITER_SCHEMA = {
    "cover": {
        "headline": "str, max 12 words",
        "category": "str, max 4 words, uppercase",
        "image_query": "str, 5-8 words for OG scrape or FLUX prompt"
    },
    "stat": {
        "eyebrow": "str, max 4 words",
        "number": "str, e.g. '$14B' or '73%'",
        "unit": "str, max 8 words",
        "context": "str, max 35 words"
    },
    "quote": {
        "text": "str, max 40 words",
        "attribution": "str, Name, Title — Organisation"
    },
    "context": {
        "kicker": "str, max 3 words",
        "headline": "str, max 15 words",
        "body": "str, max 40 words",
        "use_image": "bool"
    },
    "contrast": {
        "kicker": "str, max 3 words",
        "label_a": "str, max 3 words",
        "value_a": "str, max 20 words",
        "label_b": "str, max 3 words",
        "value_b": "str, max 20 words",
        "takeaway": "str, max 25 words"
    },
    "timeline": {
        "kicker": "str, max 3 words",
        "events": [
            {"date": "str", "event": "str, max 12 words"}
        ]
    },
    "explainer": {
        "kicker": "str, max 3 words",
        "question": "str, max 15 words",
        "answer": "str, max 55 words"
    },
    "signal": {
        "kicker": "str, max 3 words",
        "headline": "str, max 15 words",
        "implication": "str, max 45 words",
        "tag": "str, max 4 words"
    },
    "caption": (
        "str, 3-4 sentences summarising the story for Instagram. "
        "Written in third person. Factual, no hype. Max 60 words. "
        "Do NOT mention The Frameshift or @ai.xr.frameshift."
    ),
}

# ── WRITER PROMPT TEMPLATE ───────────────────────────────────────────────────
WRITER_PROMPT = """
You are a carousel editor for The Frameshift, an intelligence publication covering
AI, spatial computing, AR, and emerging technology.

Given the article content below, produce a carousel that tells the story clearly
and compellingly for an Instagram audience that is technically literate but not
specialist.

SLIDE PALETTE — choose 2 to 6 content slides after the cover:
- stat: use when there is a single number that reframes the story
- quote: use when a direct quote carries more weight than paraphrase
- context: use when the reader needs to know what happened before anything else
- contrast: use when two competing things are the core tension
- timeline: use when sequence and momentum matter
- explainer: use when the reader needs a concept explained before the point lands
- signal: use for one forward-looking implication

RULES:
- Never use more than 2 of the same slide type
- If the story is thin, 2 content slides is correct — do not pad
- cover is always first; do not add a cta slide
- Every claim must come from the article — ground or abstain
- Word limits are hard limits — do not exceed them
- Output valid JSON only, no preamble, no markdown fences

OUTPUT FORMAT:
{{
  "slides": [
    {{"type": "cover", ...cover fields}},
    {{"type": "stat", ...stat fields}},
    ...content slides in narrative order...
  ]
}}

CAPTION REQUIREMENTS (top-level field, not a slide):
- Exactly 3-4 sentences
- Minimum 50 words
- Lead with the single most interesting or surprising fact
- Explain why it matters in sentence 2-3
- Third person, factual, no hype
- Do NOT restate the headline
- Do NOT mention The Frameshift or @ai.xr.frameshift
- Field name must be exactly: caption

ARTICLE:
{{article_text}}
"""
