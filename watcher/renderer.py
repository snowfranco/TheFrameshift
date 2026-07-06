"""
Frameshift v2 — Carousel Renderer
Renders slide JSON to 1080x1350px PNG files using Pillow.
"""

import os
from PIL import Image, ImageDraw, ImageFont

# ── PATHS ────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
FONT_DIR   = os.path.join(BASE_DIR, "fonts")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── FONTS ─────────────────────────────────────────────────────────────────────
def _f(name):
    custom = os.path.join(FONT_DIR, name)
    return custom if os.path.exists(custom) and os.path.getsize(custom) > 1000 else None

FONTS = {
    "serif":        _f("EBGaramond-Regular.ttf")  or "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "serif_italic": _f("EBGaramond-Italic.ttf")   or "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
    "serif_bold":   _f("EBGaramond-Bold.ttf")      or "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "sans":         _f("DMSans-Regular.ttf")       or "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "sans_med":     _f("DMSans-Medium.ttf")        or "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "sans_bold":    _f("DMSans-Bold.ttf")          or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}

def font(role, size):
    return ImageFont.truetype(FONTS[role], size)

# ── COLOURS ───────────────────────────────────────────────────────────────────
BLACK       = (0,   0,   0)
NEAR_BLACK  = (13,  13,  13)
OFF_WHITE   = (247, 244, 239)
WHITE       = (255, 255, 255)
ACCENT      = (184, 169, 217)
ACCENT_DARK = (122, 106, 170)
RED         = (255, 49,  49)     # #ff3131
RULE_COLOR  = (232, 227, 218)
MUTED       = (153, 153, 153)
BODY        = (85,  85,  85)
DARK        = (26,  26,  26)
LABEL       = (187, 187, 187)
DIM         = (204, 204, 204)
CONTRAST_A        = (13,  13,  13)
CONTRAST_B        = (238, 232, 224)
CONTRAST_B_BORDER = (221, 215, 204)
SIGNAL_TAG_BG     = (237, 232, 245)
SIGNAL_TAG_BORDER = (208, 196, 232)
QUOTE_MARK_COLOR  = (232, 224, 240)
COVER_BORDER_L    = (120,  75, 220)   # purple
COVER_BORDER_R    = (245, 100,  40)   # orange
COVER_BORDER_W    = 14

# ── CANVAS ────────────────────────────────────────────────────────────────────
W, H     = 1080, 1350
PAD      = 66
HEADER_H = 115
ARROW_Y        = H - 72    # y-position of bottom arrow on all content slides
CONTENT_BOTTOM = ARROW_Y - 24  # hard safe-zone ceiling — no content pixel may cross this
KICKER_SIZE    = 76      # 90 * 0.85 — used for all slide kickers/eyebrows

# ── HELPERS ───────────────────────────────────────────────────────────────────
def new_slide(bg=OFF_WHITE):
    img = Image.new("RGB", (W, H), bg)
    return img, ImageDraw.Draw(img)

def _wrap_text(draw, text, max_w, font_obj):
    """Return list of wrapped line strings that each fit within max_w px."""
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        if draw.textlength(test, font=font_obj) <= max_w:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines

def draw_text_wrapped(draw, text, x, y, max_w, font_obj, color, line_gap=8, max_y=None):
    """
    Wrap and draw text. Returns y past the visual bottom of the last drawn line.
    max_y: if set, lines whose draw-point would reach or exceed max_y are skipped.
    """
    lines = _wrap_text(draw, text, max_w, font_obj)
    for i, line in enumerate(lines):
        if max_y is not None and y >= max_y:
            break
        draw.text((x, y), line, font=font_obj, fill=color)
        bbox = font_obj.getbbox(line)
        if i < len(lines) - 1:
            y += (bbox[3] - bbox[1]) + line_gap  # inter-line: visual height + gap
        else:
            y += bbox[3]                          # after last line: past visual bottom
    return y

def draw_content_header(draw):
    """Wordmark in ACCENT_DARK + hairline rule — shared by all content slides."""
    draw.text((PAD, 60), "The Frameshift", font=font("sans_bold", 33), fill=ACCENT_DARK)
    draw.line([(PAD, HEADER_H), (W - PAD, HEADER_H)], fill=RULE_COLOR, width=3)

def draw_eyebrow(draw, text, x, y, color=LABEL, size=30, max_w=None):
    """Uppercase label. Wraps if wider than max_w. Returns y past visual bottom + 14px gap."""
    f = font("sans_bold", size)
    t = text.upper()
    effective_max_w = max_w if max_w is not None else (W - PAD * 2)
    lines = _wrap_text(draw, t, effective_max_w, f) if draw.textlength(t, font=f) > effective_max_w else [t]
    for i, line in enumerate(lines):
        draw.text((x, y), line, font=f, fill=color)
        bbox = f.getbbox(line)
        if i < len(lines) - 1:
            y += (bbox[3] - bbox[1]) + 8
        else:
            y += bbox[3]
    return y + 14

def draw_pill(draw, text, x, y, border_color, text_color, radius=30, pad_x=30, pad_y=12):
    f = font("sans_med", 28)
    tw = int(draw.textlength(text, font=f))
    pill_w = tw + pad_x * 2
    pill_h = 52
    draw.rounded_rectangle([x, y, x + pill_w, y + pill_h], radius=radius,
                            outline=border_color, width=2)
    draw.text((x + pad_x, y + pad_y), text, font=f, fill=text_color)
    return y + pill_h

def draw_accent_rule(draw, y, color=ACCENT, start_x=PAD):
    """Horizontal accent line ending in an arrowhead. Tip stays 36 px from right edge."""
    end_x = W - 66
    tip_x = W - 36
    draw.line([(start_x, y), (end_x, y)], fill=color, width=5)
    draw.polygon([(end_x, y - 12), (tip_x, y), (end_x, y + 12)], fill=color)

def _draw_gradient_border(img, border_w, color_l, color_r):
    """Paint a left-to-right gradient border in-place. Efficient: one putpixel loop per row."""
    w, h = img.size
    # Build a single-row gradient, then stamp it as top and bottom strips
    grad_row = Image.new("RGB", (w, 1))
    for x in range(w):
        t = x / (w - 1)
        grad_row.putpixel((x, 0), tuple(int(color_l[i] + t * (color_r[i] - color_l[i])) for i in range(3)))
    border_strip = grad_row.resize((w, border_w), Image.NEAREST)
    img.paste(border_strip, (0, 0))
    img.paste(border_strip, (0, h - border_w))
    # Solid left and right edges (colors don't change along the axis)
    img.paste(Image.new("RGB", (border_w, h - 2 * border_w), color_l), (0, border_w))
    img.paste(Image.new("RGB", (border_w, h - 2 * border_w), color_r), (w - border_w, border_w))


def paste_image(base_img, img_path_or_obj, x, y, w, h):
    """Center-crop an image to fill (w × h) and paste onto base_img at (x, y)."""
    if isinstance(img_path_or_obj, str):
        try:
            img = Image.open(img_path_or_obj).convert("RGB")
        except Exception:
            base_img.paste(Image.new("RGB", (w, h), (220, 215, 208)), (x, y))
            return
    else:
        img = img_path_or_obj.convert("RGB")

    src_r = img.width / img.height
    dst_r = w / h
    if src_r > dst_r:
        nw = int(img.height * dst_r)
        img = img.crop(((img.width - nw) // 2, 0, (img.width - nw) // 2 + nw, img.height))
    else:
        nh = int(img.width / dst_r)
        img = img.crop((0, (img.height - nh) // 2, img.width, (img.height - nh) // 2 + nh))
    base_img.paste(img.resize((w, h), Image.LANCZOS), (x, y))


# ── SLIDE RENDERERS ───────────────────────────────────────────────────────────

def render_cover(data, image_obj=None, logo_obj=None):
    img = Image.new("RGB", (W, H), NEAR_BLACK)
    draw = ImageDraw.Draw(img)

    if image_obj:
        paste_image(img, image_obj, 0, 0, W, H)
    else:
        img.paste(Image.new("RGB", (W, H), (30, 30, 35)), (0, 0))

    # bottom-heavy gradient overlay
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(60):
        t = i / 60
        alpha = int(38 + (217 - 38) * (t ** 1.6))
        y0, y1 = int(H * i / 60), int(H * (i + 1) / 60)
        od.rectangle([(0, y0), (W, y1)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    draw.text((PAD, 66), "The Frameshift", font=font("sans_bold", 45), fill=WHITE)

    # headline — dynamic size, fills ~bottom third
    headline = data.get("headline", "")
    max_w    = W - PAD * 2
    HEADLINE_ZONE = 330
    pill_h, rule_gap, bottom_pad = 54, 36, 66

    def _wrap_hl(size):
        f = font("serif", size)
        wds, cur, lines = headline.split(), [], []
        for w_ in wds:
            test = " ".join(cur + [w_])
            if draw.textlength(test, font=f) <= max_w:
                cur.append(w_)
            else:
                if cur: lines.append(" ".join(cur))
                cur = [w_]
        if cur: lines.append(" ".join(cur))
        lh = f.getbbox("Ag")[3] - f.getbbox("Ag")[1] + 10
        return lines, lh, f

    for size in range(96, 54, -4):
        lines, line_h, f_hl = _wrap_hl(size)
        if len(lines) * line_h <= HEADLINE_ZONE:
            break

    block_h = len(lines) * line_h + 24 + pill_h + rule_gap + 5

    if logo_obj is not None:
        r, g, b, a = logo_obj.split()
        a = a.point(lambda x: int(x * 0.85))
        logo_rgba = Image.merge("RGBA", (r, g, b, a))
        lw, lh_ = logo_obj.width * 3, logo_obj.height * 3
        logo_scaled = logo_rgba.resize((lw, lh_), Image.LANCZOS)
        img.paste(logo_scaled, (PAD, H - bottom_pad - block_h - lh_ - 60), logo_scaled)

    text_y = H - bottom_pad - block_h
    for line in lines:
        draw.text((PAD, text_y), line, font=f_hl, fill=WHITE)
        text_y += line_h
    text_y += 24

    draw_pill(draw, data.get("category", "").upper(), PAD, text_y,
              border_color=(184, 169, 217, 140), text_color=(200, 188, 230), radius=30)

    # Arrow starts at 1/3 of canvas width — does not run corner-to-corner
    draw_accent_rule(draw, H - bottom_pad, color=ACCENT, start_x=W // 3)
    _draw_gradient_border(img, COVER_BORDER_W, COVER_BORDER_L, COVER_BORDER_R)
    return img


def render_stat(data, image_obj=None):
    img, draw = new_slide(OFF_WHITE)
    draw_content_header(draw)

    f_num  = font("serif_bold", 260)
    f_unit = font("sans_bold", KICKER_SIZE)
    f_body = font("sans", 45)

    y = 165
    y = draw_eyebrow(draw, data.get("eyebrow", ""), PAD, y, color=RED, size=KICKER_SIZE)
    y += 12

    number = data.get("number", "")
    draw.text((PAD, y), number, font=f_num, fill=NEAR_BLACK)
    num_bbox = f_num.getbbox(number) if number else (0, 0, 0, 60)
    y += num_bbox[3] + 24   # advance past visual bottom of glyph (bbox[3] = offset from draw point to bottom pixel)

    y = draw_text_wrapped(draw, data.get("unit", ""), PAD, y,
                          W - PAD * 2, f_unit, RED, line_gap=8)
    y += 28

    # Context body sits above the image zone
    if image_obj is not None:
        IMG_H   = 290
        IMG_TOP = ARROW_Y - IMG_H - 16
        body_limit = IMG_TOP - 16
    else:
        body_limit = ARROW_Y - 20

    if y < body_limit:
        draw_text_wrapped(draw, data.get("context", ""), PAD, y,
                          W - PAD * 2, f_body, BODY, line_gap=18, max_y=body_limit)

    if image_obj is not None:
        paste_image(img, image_obj, PAD, IMG_TOP, W - PAD * 2, IMG_H)

    draw_accent_rule(draw, ARROW_Y, start_x=PAD)
    return img


def render_quote(data):
    img, draw = new_slide(OFF_WHITE)
    draw_content_header(draw)

    inner_x     = PAD + 36
    inner_max_w = W - inner_x - PAD

    # Left accent bar
    draw.rectangle([(PAD, 204), (PAD + 6, H - 200)], fill=ACCENT)
    # Decorative quote mark
    draw.text((inner_x, 195), "\u201c", font=font("serif", 210), fill=QUOTE_MARK_COLOR)

    text        = data.get("text", "")
    attribution = data.get("attribution", "")

    # Fixed size — decoupled from quote size to prevent overlap on short quotes
    attrib_size  = 62
    f_attrib     = font("sans_med", attrib_size)
    attrib_lh    = f_attrib.getbbox("Ag")[3] - f_attrib.getbbox("Ag")[1] + 10
    attrib_lines = _wrap_text(draw, attribution, inner_max_w, f_attrib)
    attrib_block = len(attrib_lines) * attrib_lh
    attrib_y     = ARROW_Y - attrib_block - 44

    # Quote zone derived from actual attribution position
    quote_zone = attrib_y - 24 - 310

    # Shrink quote font until it fits; max_y guards against rounding overruns
    best_size = 48
    for size in range(96, 46, -4):
        f_q   = font("serif_italic", size)
        lines = _wrap_text(draw, text, inner_max_w, f_q)
        lh    = f_q.getbbox("Ag")[3] - f_q.getbbox("Ag")[1] + 24
        if len(lines) * lh <= quote_zone:
            best_size = size
            break

    draw_text_wrapped(draw, text, inner_x, 310, inner_max_w,
                      font("serif_italic", best_size), DARK, line_gap=24,
                      max_y=attrib_y - 16)

    # Attribution — red, wrapped, bottom-anchored
    for i, line in enumerate(attrib_lines):
        draw.text((inner_x, attrib_y + i * attrib_lh), line, font=f_attrib, fill=RED)

    draw_accent_rule(draw, ARROW_Y, start_x=PAD)
    return img


def render_context(data, image_obj=None):
    img, draw = new_slide(OFF_WHITE)
    draw_content_header(draw)

    y = 150
    y = draw_eyebrow(draw, data.get("kicker", "What happened"), PAD, y, RED, size=KICKER_SIZE)
    y += 14

    has_image = data.get("use_image", False) and image_obj is not None

    y = draw_text_wrapped(draw, data.get("headline", ""), PAD, y,
                          W - PAD * 2, font("serif", 86), NEAR_BLACK, line_gap=14)
    y += 38

    if has_image:
        img_h = 360
        paste_image(img, image_obj, PAD, y, W - PAD * 2, img_h)
        y += img_h + 28
        f_body = font("sans", 37)
    else:
        f_body = font("sans", 43)   # more space — slightly larger body

    if y < CONTENT_BOTTOM:
        draw_text_wrapped(draw, data.get("body", ""), PAD, y,
                          W - PAD * 2, f_body, BODY, line_gap=16, max_y=CONTENT_BOTTOM)

    draw_accent_rule(draw, ARROW_Y, start_x=PAD)
    return img


def render_contrast(data):
    img, draw = new_slide(OFF_WHITE)
    draw_content_header(draw)

    y = 150
    y = draw_eyebrow(draw, data.get("kicker", "The divide"), PAD, y, RED, size=KICKER_SIZE)
    y += 20

    cell_w  = (W - PAD * 2 - 24) // 2
    inner_w = cell_w - 66
    f_val   = font("serif", 46)
    f_lbl   = font("sans_bold", 27)
    val_lh  = (f_val.getbbox("Ag")[3] - f_val.getbbox("Ag")[1]) + 10

    # Cell height expands to fit the tallest side — never clips content
    max_val_lines = max(
        len(_wrap_text(draw, data.get("value_a", ""), inner_w, f_val)),
        len(_wrap_text(draw, data.get("value_b", ""), inner_w, f_val)),
    )
    cell_h = max(90 + max_val_lines * val_lh + 40, 280)

    cells = [
        ("label_a", "value_a", CONTRAST_A, None,               (102, 102, 102), WHITE),
        ("label_b", "value_b", CONTRAST_B, CONTRAST_B_BORDER,  (187, 187, 187), NEAR_BLACK),
    ]
    for i, (key_l, key_v, bg, border, label_c, val_c) in enumerate(cells):
        cx = PAD + i * (cell_w + 24)
        if border:
            draw.rounded_rectangle([cx, y, cx + cell_w, y + cell_h],
                                   radius=9, fill=bg, outline=border, width=2)
        else:
            draw.rounded_rectangle([cx, y, cx + cell_w, y + cell_h], radius=9, fill=bg)
        draw.text((cx + 33, y + 36), data.get(key_l, "").upper(), font=f_lbl, fill=label_c)
        draw_text_wrapped(draw, data.get(key_v, ""), cx + 33, y + 90, inner_w, f_val, val_c, line_gap=10)

    y += cell_h + 36
    draw_text_wrapped(draw, data.get("takeaway", ""), PAD, y,
                      W - PAD * 2, font("sans", 42), (68, 68, 68), line_gap=16,
                      max_y=CONTENT_BOTTOM)

    draw_accent_rule(draw, ARROW_Y, start_x=PAD)
    return img


def render_timeline(data):
    img, draw = new_slide(OFF_WHITE)
    draw_content_header(draw)

    y = 150
    y = draw_eyebrow(draw, data.get("kicker", "How we got here"), PAD, y, RED, size=KICKER_SIZE)
    y += 20

    events = data.get("events", [])
    dot_x, text_x, dot_r = PAD + 12, PAD + 48, 12

    for i, event in enumerate(events):
        is_last   = (i == len(events) - 1)
        dot_color = NEAR_BLACK if is_last else ACCENT_DARK

        draw.ellipse([(dot_x - dot_r, y), (dot_x + dot_r, y + dot_r * 2)], fill=dot_color)
        draw.text((text_x, y - 3), event.get("date", ""),
                  font=font("sans_bold", 30), fill=dot_color)

        event_y = y + 36
        event_y = draw_text_wrapped(draw, event.get("event", ""), text_x, event_y,
                                    W - text_x - PAD, font("sans", 37), DARK, line_gap=8,
                                    max_y=CONTENT_BOTTOM)
        if not is_last:
            line_top = y + dot_r * 2 + 6
            line_bot = event_y + 24
            draw.line([(dot_x, line_top), (dot_x, line_bot)], fill=RULE_COLOR, width=3)
            y = line_bot + 12
        else:
            y = event_y + 12

    draw_accent_rule(draw, ARROW_Y, start_x=PAD)
    return img


def render_explainer(data):
    img, draw = new_slide(OFF_WHITE)
    draw_content_header(draw)

    y = 150
    y = draw_eyebrow(draw, data.get("kicker", "Worth knowing"), PAD, y, RED, size=KICKER_SIZE)
    y += 14

    y = draw_text_wrapped(draw, data.get("question", ""), PAD, y,
                          W - PAD * 2, font("serif", 86), NEAR_BLACK, line_gap=14)
    y += 38

    draw.line([(PAD, y), (W - PAD, y)], fill=RULE_COLOR, width=3)
    y += 36

    answer = data.get("answer", "").replace("**", "")
    draw_text_wrapped(draw, answer, PAD, y,
                      W - PAD * 2, font("sans", 42), (58, 58, 58), line_gap=14,
                      max_y=CONTENT_BOTTOM)

    draw_accent_rule(draw, ARROW_Y, start_x=PAD)
    return img


def render_signal(data):
    img, draw = new_slide(OFF_WHITE)
    draw_content_header(draw)

    y = 150
    y = draw_eyebrow(draw, data.get("kicker", "What this means"), PAD, y, RED, size=KICKER_SIZE)
    y += 20

    hl_text   = data.get("headline", "")
    impl_text = data.get("implication", "")

    # Estimate how much vertical space the implication + tag need
    f_impl    = font("sans", 45)
    impl_wrap = _wrap_text(draw, impl_text, W - PAD * 2, f_impl)
    bb_impl   = f_impl.getbbox("Ag")
    impl_lh   = (bb_impl[3] - bb_impl[1]) + 20
    impl_h    = (max(len(impl_wrap) - 1, 0) * impl_lh + bb_impl[3]) if impl_wrap else 0
    reserved  = 48 + impl_h + 40 + 80   # gap + implication + gap + tag clearance
    hl_budget = CONTENT_BOTTOM - y - reserved

    # Auto-shrink headline from 126 → 72 until it fits the budget
    best_hl_size = 72
    for size in range(126, 66, -6):
        f_hl  = font("serif", size)
        lines = _wrap_text(draw, hl_text, W - PAD * 2, f_hl)
        bb    = f_hl.getbbox("Ag")
        lh    = (bb[3] - bb[1]) + 18
        total = (max(len(lines) - 1, 0) * lh + bb[3]) if lines else 0
        if total <= hl_budget:
            best_hl_size = size
            break

    y = draw_text_wrapped(draw, hl_text, PAD, y,
                          W - PAD * 2, font("serif", best_hl_size), NEAR_BLACK,
                          line_gap=18, max_y=CONTENT_BOTTOM)
    y += 48

    y = draw_text_wrapped(draw, impl_text, PAD, y,
                          W - PAD * 2, f_impl, BODY,
                          line_gap=20, max_y=CONTENT_BOTTOM)
    y += 40

    tag = data.get("tag", "").upper()
    if tag and y <= CONTENT_BOTTOM - 54:
        f_tag  = font("sans_bold", 30)
        tw     = int(draw.textlength(tag, font=f_tag))
        pill_w = tw + 60
        draw.rounded_rectangle([PAD, y, PAD + pill_w, y + 54], radius=27,
                               fill=SIGNAL_TAG_BG, outline=SIGNAL_TAG_BORDER, width=2)
        draw.text((PAD + 30, y + 12), tag, font=f_tag, fill=ACCENT_DARK)

    draw_accent_rule(draw, ARROW_Y, start_x=PAD)
    return img


def render_cta(data):
    img, draw = new_slide(BLACK)

    cx, cy = W // 2, H // 2
    rule_y = cy - 180
    rule_w = 240
    draw.line([(cx - rule_w // 2, rule_y), (cx + rule_w // 2, rule_y)],
              fill=(255, 255, 255, 64), width=3)

    handle = "@ai.xr.frameshift"
    f_h = font("sans", 33)
    draw.text((cx - draw.textlength(handle, font=f_h) // 2, rule_y + 30),
              handle, font=f_h, fill=(115, 115, 115))

    headline = data.get("headline", "Follow for weekly signal.")
    f_hl     = font("serif_bold", 102)
    max_w    = W - PAD * 3
    wds, cur, lines = headline.split(), [], []
    for w_ in wds:
        test = " ".join(cur + [w_])
        if draw.textlength(test, font=f_hl) <= max_w:
            cur.append(w_)
        else:
            if cur: lines.append(" ".join(cur))
            cur = [w_]
    if cur: lines.append(" ".join(cur))

    line_h  = f_hl.getbbox("Ag")[3] - f_hl.getbbox("Ag")[1] + 18
    text_y  = cy - (len(lines) * line_h) // 2 + 60
    for line in lines:
        draw.text((cx - draw.textlength(line, font=f_hl) // 2, text_y),
                  line, font=f_hl, fill=WHITE)
        text_y += line_h

    return img


# ── SLIDE DISPATCH ────────────────────────────────────────────────────────────
RENDERERS = {
    "cover":     render_cover,
    "stat":      render_stat,
    "quote":     render_quote,
    "context":   render_context,
    "contrast":  render_contrast,
    "timeline":  render_timeline,
    "explainer": render_explainer,
    "signal":    render_signal,
    "cta":       render_cta,
}

def render_carousel(slides_json, image_obj=None, output_dir=OUTPUT_DIR, prefix="slide",
                    logo_obj=None, stat_image_obj=None):
    """
    slides_json:    list of slide dicts.
    image_obj:      PIL Image for cover + context slides.
    stat_image_obj: PIL Image for stat slide bottom image.
    Returns list of saved PNG paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = []

    for i, slide in enumerate(slides_json):
        stype    = slide.get("type")
        renderer = RENDERERS.get(stype)
        if not renderer:
            print(f"[renderer] unknown slide type: {stype}, skipping")
            continue

        if stype == "cover":
            img = renderer(slide, image_obj=image_obj, logo_obj=logo_obj)
        elif stype == "context":
            img = renderer(slide, image_obj=image_obj)
        elif stype == "stat":
            img = renderer(slide, image_obj=stat_image_obj)
        else:
            img = renderer(slide)

        path = os.path.join(output_dir, f"{prefix}_{i+1:02d}_{stype}.png")
        img.save(path, "PNG", quality=95)
        print(f"[renderer] saved {path}")
        paths.append(path)

    return paths


# ── TEST FIXTURE ──────────────────────────────────────────────────────────────
TEST_CAROUSEL = [
    {
        "type": "cover",
        "headline": "Asus and Xreal just launched dedicated AR glasses for gamers.",
        "category": "Hardware & Spatial Computing",
        "image_query": "AR glasses gamer futuristic desk setup"
    },
    {
        "type": "stat",
        "eyebrow": "Market Signal",
        "number": "$14B",
        "unit": "projected AR hardware market by 2028",
        "context": "That number was $3B in 2022. The Asus-Xreal launch is the clearest signal yet that dedicated gaming hardware is the entry point."
    },
    {
        "type": "quote",
        "text": "We're not building AR glasses. We're building the next display category — one that happens to sit on your face.",
        "attribution": "Chi Xu, CEO — Xreal"
    },
    {
        "type": "context",
        "kicker": "What happened",
        "headline": "Asus partnered with Xreal to ship the ROG AR glasses — first device built exclusively for gaming.",
        "body": "Runs at 120Hz, pairs directly with the ROG Ally, ships without a tethered phone. First time a major PC brand has co-designed AR hardware from the ground up.",
        "use_image": False
    },
    {
        "type": "contrast",
        "kicker": "The divide",
        "label_a": "Old model",
        "value_a": "Phone-dependent. General purpose. Nobody's primary device.",
        "label_b": "New model",
        "value_b": "Standalone. Use-case specific. Designed to win one vertical first.",
        "takeaway": "Xreal's bet: depth before breadth. Gaming is the beachhead, not the ceiling."
    },
    {
        "type": "timeline",
        "kicker": "How we got here",
        "events": [
            {"date": "2021", "event": "Xreal launches Air — first consumer waveguide glasses, phone-only"},
            {"date": "2023", "event": "Air 2 Pro adds electrochromic dimming, still tethered"},
            {"date": "2024", "event": "Asus partnership announced — first OEM co-design"},
            {"date": "2025", "event": "ROG AR glasses ship — standalone, gaming-first"}
        ]
    },
    {
        "type": "signal",
        "kicker": "What this means",
        "headline": "Gaming is AR's iPhone moment — the killer app that makes the hardware make sense.",
        "implication": "Every major display category found its early adopters in gaming: high-refresh monitors, 4K, HDR. AR is following the same path. Brands that build gaming-first will have the scale to move into enterprise next.",
        "tag": "Watch this space"
    },
    {
        "type": "cta",
        "headline": "The AR gaming era just started. Follow to track where it goes."
    }
]


if __name__ == "__main__":
    print("[renderer] rendering test carousel...")
    paths = render_carousel(TEST_CAROUSEL, prefix="test")
    print(f"[renderer] done — {len(paths)} slides")
