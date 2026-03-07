from __future__ import annotations

from datetime import datetime
from io import BytesIO
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 1600, 900
SS = 2

TOKENS = {
    "BG_BASE": "#081423",
    "BG_DEEP": "#04101D",
    "BG_MID": "#0C2238",
    "BG_VIOLET": "#1A1F44",
    "GLASS_FILL_MAIN": (220, 235, 255, 41),
    "GLASS_FILL_LIGHT": (235, 245, 255, 51),
    "GLASS_FILL_SOFT": (190, 220, 255, 25),
    "GLASS_FILL_DARK": (30, 40, 70, 46),
    "GLASS_BORDER_MAIN": (255, 255, 255, 56),
    "GLASS_BORDER_SOFT": (255, 255, 255, 30),
    "GLASS_TOP_HIGHLIGHT": (255, 255, 255, 66),
    "GLASS_EDGE_GLOW": (180, 220, 255, 46),
    "TEXT_PRIMARY": (247, 251, 255, 255),
    "TEXT_SECONDARY": (214, 228, 245, 255),
    "TEXT_MUTED": (175, 195, 217, 255),
    "TEXT_DARK_ON_LIGHT": (27, 36, 48, 255),
    "POSITIVE": (99, 245, 210, 255),
    "NEGATIVE": (255, 141, 168, 255),
    "WARNING": (255, 211, 107, 255),
}


def _hex(v: str, a: int = 255):
    v = v.lstrip("#")
    return (int(v[:2], 16), int(v[2:4], 16), int(v[4:6], 16), a)


FONT_PATHS = {
    "bold": ["/usr/share/fonts/truetype/inter/Inter-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "semibold": ["/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "medium": ["/usr/share/fonts/truetype/inter/Inter-Medium.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "regular": ["/usr/share/fonts/truetype/inter/Inter-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


@lru_cache(maxsize=512)
def font(size: int, weight: str = "regular"):
    for p in FONT_PATHS.get(weight, FONT_PATHS["regular"]):
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


@lru_cache(maxsize=256)
def rounded_mask(size: tuple[int, int], radius: int):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return m


def measure(draw: ImageDraw.ImageDraw, text: str, f):
    b = draw.textbbox((0, 0), text, font=f)
    return b[2] - b[0], b[3] - b[1]


def fit_text_to_width(text: str, start_size: int, min_size: int, max_width: int, weight: str = "regular", ellipsis: bool = True):
    text = (text or "—").strip() or "—"
    d = ImageDraw.Draw(Image.new("RGBA", (16, 16), (0, 0, 0, 0)), "RGBA")
    for s in range(start_size, min_size - 1, -1):
        f = font(s, weight)
        if measure(d, text, f)[0] <= max_width:
            return text, f
    f = font(min_size, weight)
    if not ellipsis:
        return text, f
    for i in range(len(text), 0, -1):
        t = text[:i].rstrip() + "…"
        if measure(d, t, f)[0] <= max_width:
            return t, f
    return "…", f


def _safe_i(v, d=0):
    try:
        return int(v)
    except Exception:
        return d


def format_money(v: Any) -> str:
    try:
        return f"{int(round(float(v))):,}".replace(",", " ") + " ₽"
    except Exception:
        return "—"


def format_update_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y в %H:%M")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime("%d.%m.%Y в %H:%M")
        except Exception:
            pass
    return datetime.now().strftime("%d.%m.%Y в %H:%M")


def format_tempo(value: Any) -> tuple[str, tuple[int, int, int, int]]:
    if value is None or value == "":
        return "—", TOKENS["TEXT_SECONDARY"]
    try:
        v = float(value)
        pct = int(round(v * 100)) if v <= 3.0 else int(round(v))
    except Exception:
        t = str(value).strip().replace("%", "")
        if not t:
            return "—", TOKENS["TEXT_SECONDARY"]
        try:
            pct = int(float(t))
        except Exception:
            return "—", TOKENS["TEXT_SECONDARY"]
    pct = max(0, min(250, pct))
    if pct >= 102:
        c = TOKENS["POSITIVE"]
    elif pct <= 97:
        c = TOKENS["NEGATIVE"]
    else:
        c = TOKENS["TEXT_SECONDARY"]
    return f"{pct}%", c


THEME = {
    "BG_1": "#08111F",
    "BG_2": "#0B1424",
    "BG_3": "#101A2C",
    "BG_4": "#172235",
    "TEXT_PRIMARY": _hex("#F4F8FF"),
    "TEXT_SECONDARY": _hex("#B8C4DA"),
    "TEXT_MUTED": _hex("#8D99B4"),
    "GLASS_FILL_MAIN": (22, 30, 50, 173),
    "GLASS_FILL_SOFT": (24, 34, 56, 148),
    "GLASS_FILL_LIGHT": (255, 255, 255, 11),
    "BORDER_SOFT": (255, 255, 255, 26),
    "BORDER_MAIN": (180, 215, 255, 56),
    "BORDER_BRIGHT": (215, 235, 255, 87),
    "CYAN_1": _hex("#45E6FF"),
    "CYAN_2": _hex("#78F2FF"),
    "BLUE_1": _hex("#2F8CFF"),
    "BLUE_2": _hex("#5A7DFF"),
    "VIOLET_1": _hex("#7B61FF"),
    "VIOLET_2": _hex("#A78BFF"),
    "GREEN_1": _hex("#24D977"),
    "GREEN_2": _hex("#51F5A2"),
    "GOLD_1": _hex("#FFB648"),
    "GOLD_2": _hex("#FFD36E"),
    "GOLD_3": _hex("#FF9F1C"),
    "STATUS_ACTIVE_DOT": _hex("#22E27A"),
    "STATUS_ACTIVE_GLOW": (34, 226, 122, 102),
    "GLOW_CYAN": (69, 230, 255, 86),
    "GLOW_BLUE": (47, 140, 255, 76),
    "GLOW_VIOLET": (123, 97, 255, 71),
    "GLOW_GREEN": (36, 217, 119, 71),
    "GLOW_GOLD": (255, 182, 72, 76),
}


def background(width: int, height: int):
    """Legacy background for leaderboard renderer."""
    img = Image.new("RGBA", (width, height), _hex(TOKENS["BG_BASE"]))
    d = ImageDraw.Draw(img, "RGBA")
    top, bot = _hex(TOKENS["BG_DEEP"]), _hex(TOKENS["BG_MID"])
    for y in range(height):
        t = y / max(1, height - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line((0, y, width, y), fill=c)

    g = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g, "RGBA")
    glows = [
        ((-260, -250, width // 2, height // 2), "#63DFFF", 56),
        ((width // 3, -180, width + 180, height // 2), "#8C7CFF", 52),
        ((-180, height // 2 - 130, width // 2 + 160, height + 230), "#73FFD8", 46),
    ]
    for box, col, a in glows:
        gd.ellipse(box, fill=_hex(col, a))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(150)))
    return img


def draw_glow(canvas: Image.Image, box: tuple[int, int, int, int], color: tuple[int, int, int, int], blur: int):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer, "RGBA")
    ld.rounded_rectangle(box, radius=max(8, min((box[2] - box[0]) // 4, (box[3] - box[1]) // 2)), fill=color)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def draw_inner_highlight(card: Image.Image, radius: int):
    w, h = card.size
    d = ImageDraw.Draw(card, "RGBA")
    d.line((22, 14, w - 24, 14), fill=(255, 255, 255, 26), width=2)
    d.rounded_rectangle((1, 1, w - 2, h - 2), radius=max(8, radius - 2), outline=(255, 255, 255, 9), width=1)


def draw_glass_card(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
    border: tuple[int, int, int, int],
    shadow_alpha: int = 86,
    shadow_blur: int = 34,
    shadow_offset_y: int = 16,
    glow: tuple[tuple[int, int, int, int], int] | None = None,
):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1

    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh, "RGBA")
    sd.rounded_rectangle((x1, y1 + shadow_offset_y, x2, y2 + shadow_offset_y), radius=radius, fill=(0, 0, 0, shadow_alpha))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(shadow_blur)))
    if glow:
        draw_glow(canvas, (x1 + 10, y1 + 10, x2 - 10, y2 - 2), glow[0], glow[1])

    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=fill, outline=border, width=1)

    top_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(top_overlay, "RGBA")
    for y in range(h):
        a = int(max(0, 26 * (1 - y / max(1, h - 1))))
        if a:
            td.line((0, y, w, y), fill=(255, 255, 255, a))
    card.alpha_composite(top_overlay)
    draw_inner_highlight(card, radius)
    canvas.alpha_composite(card, (x1, y1))


def _progress_ratio(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        p = float(value)
    except Exception:
        return 0.0
    if p > 1.0:
        p = p / 100.0
    return max(0.0, min(1.0, p))


def draw_progress_bar(canvas: Image.Image, box: tuple[int, int, int, int], completion: Any):
    x1, y1, x2, y2 = box
    h = y2 - y1
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rounded_rectangle(box, radius=h // 2, fill=(8, 14, 24, 143), outline=(255, 255, 255, 20), width=2)
    d.line((x1 + 8, y1 + 5, x2 - 8, y1 + 5), fill=(255, 255, 255, 16), width=2)

    p = _progress_ratio(completion)
    fw = int((x2 - x1) * p)
    if fw < 8:
        return

    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.rounded_rectangle((x1 + 2, y1 + 1, x1 + fw - 2, y2 - 1), radius=h // 2, fill=(99, 174, 255, 72))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(20)))

    fill = Image.new("RGBA", (fw, h - 6), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill, "RGBA")
    c1, c2, c3 = THEME["CYAN_1"], THEME["BLUE_1"], THEME["VIOLET_2"]
    for i in range(fw):
        t = i / max(1, fw - 1)
        if t < 0.45:
            k = t / 0.45
            c = tuple(int(c1[j] + (c2[j] - c1[j]) * k) for j in range(3)) + (255,)
        else:
            k = (t - 0.45) / 0.55
            c = tuple(int(c2[j] + (c3[j] - c2[j]) * k) for j in range(3)) + (255,)
        fd.line((i, 0, i, h - 6), fill=c)
    fd.line((8, 3, fw - 8, 3), fill=(255, 255, 255, 48), width=2)
    canvas.paste(fill, (x1, y1 + 3), rounded_mask((fw, h - 6), (h - 6) // 2))

    g2 = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    g2d = ImageDraw.Draw(g2, "RGBA")
    ex = x1 + fw
    g2d.ellipse((ex - 18, y1 - 4, ex + 18, y2 + 4), fill=(167, 139, 255, 52))
    canvas.alpha_composite(g2.filter(ImageFilter.GaussianBlur(18)))


def draw_progress_ring(canvas: Image.Image, center: tuple[int, int], outer_d: int, thickness: int, completion: Any):
    cx, cy = center
    r = outer_d // 2
    box = (cx - r, cy - r, cx + r, cy + r)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.arc(box, start=-90, end=270, fill=(255, 255, 255, 24), width=thickness)

    p = _progress_ratio(completion)
    if p <= 0:
        return
    end = -90 + int(360 * p)

    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.arc(box, start=-90, end=end, fill=(72, 205, 255, 115), width=thickness)
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))

    steps = max(80, int(outer_d * 1.8))
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps
        a0 = -90 + int((end + 90) * t0)
        a1 = -90 + int((end + 90) * t1)
        if a0 >= end:
            break
        if t0 < 0.55:
            k = t0 / 0.55
            c1, c2 = THEME["CYAN_1"], THEME["BLUE_1"]
        else:
            k = (t0 - 0.55) / 0.45
            c1, c2 = THEME["BLUE_1"], THEME["GREEN_2"]
        col = tuple(int(c1[j] + (c2[j] - c1[j]) * k) for j in range(3)) + (255,)
        d.arc(box, start=a0, end=min(a1, end), fill=col, width=thickness)


def draw_coin_illustration(canvas: Image.Image, anchor: tuple[int, int]):
    ax, ay = anchor
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    for i in range(4):
        cx, cy = ax - i * 15, ay - i * 9
        d.ellipse((cx - 28, cy - 12, cx + 28, cy + 12), fill=(255, 182, 72, 68), outline=(255, 211, 110, 210), width=2)
        d.ellipse((cx - 20, cy - 6, cx + 20, cy + 6), outline=(255, 240, 170, 130), width=1)
    d.text((ax - 10, ay - 9), "₽", fill=(255, 220, 140, 210), font=font(20, "bold"))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1)))


def draw_calendar_shift_icon(canvas: Image.Image, box: tuple[int, int, int, int]):
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    c = (167, 139, 255, 235)
    d.rounded_rectangle((x1 + 6, y1 + 8, x2 - 18, y2 - 10), radius=12, outline=c, width=4)
    d.line((x1 + 16, y1 + 26, x2 - 28, y1 + 26), fill=(90, 125, 255, 230), width=4)
    d.ellipse((x2 - 36, y2 - 36, x2 - 4, y2 - 4), outline=(90, 125, 255, 230), width=4)
    d.line((x2 - 20, y2 - 20, x2 - 20, y2 - 30), fill=(90, 125, 255, 230), width=3)
    d.line((x2 - 20, y2 - 20, x2 - 13, y2 - 16), fill=(90, 125, 255, 230), width=3)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1)))


def draw_trend_arrow_icon(canvas: Image.Image, box: tuple[int, int, int, int]):
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    c = (81, 245, 162, 240)
    pts = [(x1 + 10, y2 - 10), (x1 + 34, y1 + 42), (x1 + 58, y1 + 36), (x2 - 14, y1 + 10)]
    d.line(pts, fill=c, width=4, joint="curve")
    d.polygon([(x2 - 20, y1 + 8), (x2 - 8, y1 + 10), (x2 - 14, y1 + 22)], fill=c)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1)))


def _draw_dashboard_background(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, height), THEME["BG_1"])
    d = ImageDraw.Draw(img, "RGBA")
    stops = [(0.0, _hex(THEME["BG_1"])), (0.4, _hex(THEME["BG_2"])), (0.72, _hex(THEME["BG_3"])), (1.0, _hex(THEME["BG_4"]))]
    for y in range(height):
        t = y / max(1, height - 1)
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                t0, c0 = stops[i]
                t1, c1 = stops[i + 1]
                k = (t - t0) / max(1e-6, (t1 - t0))
                col = tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3)) + (255,)
                d.line((0, y, width, y), fill=col)
                break

    hl = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl, "RGBA")
    hd.ellipse((820 * SS - 480 * SS, 370 * SS - 480 * SS, 820 * SS + 480 * SS, 370 * SS + 480 * SS), fill=(80, 110, 180, 25))
    img.alpha_composite(hl.filter(ImageFilter.GaussianBlur(40 * SS)))

    tx = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    td = ImageDraw.Draw(tx, "RGBA")
    step = 54 * SS
    for x in range(-height, width, step):
        td.line((x, 0, x + height, height), fill=(160, 190, 235, 9), width=2 * SS)
    img.alpha_composite(tx.filter(ImageFilter.GaussianBlur(12 * SS)))

    vignette = Image.new("L", (width, height), 0)
    vd = ImageDraw.Draw(vignette)
    vd.rectangle((0, 0, width, height), fill=46)
    vd.rounded_rectangle((170 * SS, 170 * SS, width - 170 * SS, height - 170 * SS), radius=220 * SS, fill=0)
    dark = Image.new("RGBA", (width, height), (0, 0, 0, 46))
    img = Image.composite(dark, img, vignette.filter(ImageFilter.GaussianBlur(170 * SS)))

    bloom = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bloom, "RGBA")
    bd.ellipse((390 * SS, 470 * SS, 1240 * SS, 760 * SS), fill=(72, 160, 255, 28))
    bd.ellipse((620 * SS, 500 * SS, 1350 * SS, 780 * SS), fill=(130, 120, 255, 26))
    img.alpha_composite(bloom.filter(ImageFilter.GaussianBlur(42 * SS)))
    return img


def _render_dashboard_footer_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
        except Exception:
            return value
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def render_dashboard_image_bytes(mode: str, payload: dict) -> BytesIO:
    s = SS
    c = _draw_dashboard_background(W * s, H * s)
    d = ImageDraw.Draw(c, "RGBA")

    header = (56 * s, 44 * s, (56 + 1488) * s, (44 + 116) * s)
    draw_glass_card(c, header, 34 * s, (25, 36, 60, 107), (180, 215, 255, 36))
    d.text((96 * s, 62 * s), "Дашборд", fill=THEME["TEXT_PRIMARY"], font=font(52 * s, "bold"))
    sub = payload.get("decade_title") or "1-я декада · 1–10 марта"
    st, sf = fit_text_to_width(sub, 27 * s, 22 * s, 860 * s, "medium")
    d.text((96 * s, 123 * s), st, fill=THEME["TEXT_SECONDARY"], font=sf)

    status_box = (1102 * s, 70 * s, (1102 + 306) * s, (70 + 58) * s)
    draw_glass_card(c, status_box, 29 * s, (25, 44, 54, 122), (120, 255, 200, 56), glow=(THEME["STATUS_ACTIVE_GLOW"], 22 * s), shadow_alpha=60, shadow_blur=24 * s, shadow_offset_y=8 * s)
    dot_layer = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ImageDraw.Draw(dot_layer, "RGBA").ellipse((1133 * s, 90 * s, 1151 * s, 108 * s), fill=THEME["STATUS_ACTIVE_DOT"])
    c.alpha_composite(dot_layer.filter(ImageFilter.GaussianBlur(16 * s)))
    d.ellipse((1133 * s, 90 * s, 1151 * s, 108 * s), fill=THEME["STATUS_ACTIVE_DOT"])
    d.text((1174 * s, 85 * s), "Смена активна" if mode != "closed" else "Смена закрыта", fill=THEME["TEXT_PRIMARY"], font=font(24 * s, "semibold"))

    hero = (80 * s, 190 * s, (80 + 1440) * s, (190 + 338) * s)
    draw_glass_card(c, hero, 38 * s, (18, 26, 44, 189), (150, 205, 255, 46), glow=(THEME["GLOW_BLUE"], 36 * s), shadow_blur=34 * s)
    draw_glow(c, (120 * s, 286 * s, 760 * s, 512 * s), THEME["GLOW_CYAN"], 30 * s)
    draw_glow(c, (1070 * s, 250 * s, 1450 * s, 500 * s), THEME["GLOW_VIOLET"], 32 * s)

    d.ellipse((692 * s, 238 * s, 700 * s, 246 * s), fill=THEME["GOLD_2"])
    d.text((720 * s, 242 * s), payload.get("revenue_label", "Выручка"), fill=THEME["TEXT_SECONDARY"], font=font(22 * s, "medium"), anchor="lm")

    earned = payload.get("decade_earned", payload.get("earned", 0))
    goal = payload.get("decade_goal", payload.get("goal", 0))
    main_value = payload.get("current_amount") or format_money(earned)
    target_value = payload.get("target_amount") or format_money(goal)

    main_text, main_font = fit_text_to_width(main_value, 78 * s, 64 * s, 640 * s, "bold", ellipsis=False)
    mw, mh = measure(d, main_text, main_font)
    d.text((720 * s - mw // 2, 340 * s - mh), main_text, fill=THEME["TEXT_PRIMARY"], font=main_font)

    sub_text, sub_font = fit_text_to_width(f"из {target_value}", 34 * s, 28 * s, 580 * s, "semibold", ellipsis=False)
    sw, sh = measure(d, sub_text, sub_font)
    d.text((720 * s - sw // 2, 410 * s - sh), sub_text, fill=THEME["TEXT_SECONDARY"], font=sub_font)

    completion = payload.get("completion_percent")
    draw_progress_bar(c, (150 * s, 455 * s, (150 + 1180) * s, (455 + 28) * s), completion)

    ring_center = (1230 * s, 351 * s)
    draw_progress_ring(c, ring_center, 212 * s, 22 * s, completion)
    percent_text = f"{int(round(_progress_ratio(completion) * 100))}%"
    d.text((ring_center[0], ring_center[1] - 18 * s), percent_text, fill=THEME["TEXT_PRIMARY"], font=font(54 * s, "bold"), anchor="mm")
    d.text((ring_center[0], ring_center[1] + 34 * s), "Выполнено", fill=THEME["TEXT_SECONDARY"], font=font(22 * s, "semibold"), anchor="mm")

    remaining_text = payload.get("remaining_amount") or payload.get("remaining_text") or "—"
    if remaining_text == "—" and goal:
        remaining_text = format_money(max(int(goal) - int(earned), 0))
    d.text((1188 * s, 500 * s), f"Осталось {remaining_text}", fill=THEME["TEXT_SECONDARY"], font=font(26 * s, "semibold"), anchor="ls")

    metric_rows = payload.get("decade_metrics") or payload.get("metrics") or []
    metric_map = {str(row[0]).lower(): str(row[1]) for row in metric_rows if isinstance(row, (list, tuple)) and len(row) >= 2}
    shifts_left = payload.get("shifts_left") or metric_map.get("осталось смен") or metric_map.get("смен осталось") or "—"
    per_shift_needed = payload.get("per_shift_needed") or metric_map.get("нужно в смену") or "—"

    cards = [
        ((92, 550, 566, 712), "Осталось до плана", remaining_text, THEME["GLOW_GOLD"]),
        ((582, 550, 1056, 712), "Смен осталось", str(shifts_left), THEME["GLOW_VIOLET"]),
        ((1072, 550, 1520, 712), "Нужно в смену", str(per_shift_needed), THEME["GLOW_GREEN"]),
    ]
    for i, (box_u, title, value, glow_col) in enumerate(cards):
        box = tuple(v * s for v in box_u)
        draw_glass_card(c, box, 30 * s, (20, 28, 48, 194), (170, 220, 255, 41), glow=(glow_col, 28 * s), shadow_blur=30 * s)
        tx = (128 + i * 490) * s if i < 2 else 1108 * s
        d.text((tx, 604 * s), title, fill=THEME["GREEN_2"] if i == 2 else THEME["TEXT_PRIMARY"], font=font(27 * s, "medium"), anchor="ls")
        vf = font((64 if i == 1 else 58) * s, "bold")
        vtxt, vf = fit_text_to_width(str(value), (64 if i == 1 else 58) * s, 44 * s, (240 if i != 2 else 300) * s, "bold", ellipsis=False)
        d.text((tx, 670 * s), vtxt, fill=THEME["TEXT_PRIMARY"], font=vf, anchor="ls")

    draw_coin_illustration(c, (500 * s, 660 * s))
    draw_calendar_shift_icon(c, (942 * s, 610 * s, 1020 * s, 690 * s))
    draw_trend_arrow_icon(c, (1390 * s, 615 * s, 1490 * s, 690 * s))

    stats = (92 * s, 734 * s, 1520 * s, 830 * s)
    draw_glass_card(c, stats, 30 * s, (19, 27, 45, 184), (170, 220, 255, 36), shadow_blur=26 * s, shadow_offset_y=10 * s)
    mini = payload.get("mini") or []
    g1 = mini[0] if len(mini) > 0 else f"Смен: {payload.get('shifts_done', '—')}"
    g2 = mini[1] if len(mini) > 1 else f"Машин: {payload.get('cars_done', '—')}"
    g3 = mini[2] if len(mini) > 2 else f"Средний чек: {payload.get('average_check', '—')}"
    d.text((128 * s, 782 * s), g1, fill=THEME["TEXT_SECONDARY"], font=font(26 * s, "semibold"), anchor="lm")
    d.text((530 * s, 782 * s), g2, fill=THEME["TEXT_SECONDARY"], font=font(26 * s, "semibold"), anchor="lm")
    d.text((1030 * s, 782 * s), g3, fill=THEME["TEXT_SECONDARY"], font=font(26 * s, "semibold"), anchor="lm")

    footer_text = f"Обновлено: {_render_dashboard_footer_dt(payload.get('updated_at'))}"
    d.text((800 * s, 874 * s), footer_text, fill=THEME["TEXT_MUTED"], font=font(24 * s, "medium"), anchor="ms")

    out = c.resize((W, H), Image.Resampling.LANCZOS)
    bio = BytesIO()
    bio.name = "dashboard.png"
    out.convert("RGB").save(bio, format="PNG")
    bio.seek(0)
    return bio






def draw_avatar(canvas, box, avatar, name):
    x1, y1, x2, y2 = box
    size = min(x2 - x1, y2 - y1)
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size, size), fill=255)
    if avatar is None:
        av = Image.new("RGBA", (size, size), _hex("#5C7CFF", 220))
        initials = "".join(p[:1] for p in str(name or "?").split()[:2]).upper() or "?"
        dd = ImageDraw.Draw(av, "RGBA")
        f = font(max(26, size // 3), "bold")
        tw, th = measure(dd, initials, f)
        dd.text(((size - tw) / 2, (size - th) / 2 - 1), initials, fill=TOKENS["TEXT_PRIMARY"], font=f)
    else:
        av = ImageOps.fit(avatar.convert("RGBA"), (size, size), method=Image.Resampling.LANCZOS)
    canvas.paste(av, (x1, y1), m)
    ImageDraw.Draw(canvas, "RGBA").ellipse((x1 - 3, y1 - 3, x1 + size + 3, y1 + size + 3), outline=TOKENS["GLASS_BORDER_MAIN"], width=3)


def draw_glass_panel(canvas: Image.Image, bg: Image.Image, box: tuple[int, int, int, int], radius: int, tint=(220, 235, 255, 40), border=TOKENS["GLASS_BORDER_SOFT"], glow: tuple[int, int, int, int] | None = None):
    draw_glass_card(canvas, box, radius, tint, border, glow=((glow or (80, 140, 255, 62)), 24))


def draw_glass_pill(canvas, bg, box, text, color=TOKENS["TEXT_PRIMARY"], weight="semibold"):
    draw_glass_panel(canvas, bg, box, radius=(box[3] - box[1]) // 2, tint=TOKENS["GLASS_FILL_DARK"])
    d = ImageDraw.Draw(canvas, "RGBA")
    txt, f = fit_text_to_width(text, 34, 18, box[2] - box[0] - 28, weight=weight)
    tw, th = measure(d, txt, f)
    d.text((box[0] + (box[2] - box[0] - tw) / 2, box[1] + (box[3] - box[1] - th) / 2 - 1), txt, fill=color, font=f)


def render_leaderboard_image_bytes(decade_title: str, decade_leaders: list[dict], highlight_name: str | None = None, top3_avatars: dict[int, object] | None = None, updated_at: Any | None = None) -> BytesIO:
    s = SS
    bg = background(W * s, H * s)
    c = bg.copy()
    d = ImageDraw.Draw(c, "RGBA")

    header = (52 * s, 42 * s, (W - 52) * s, 200 * s)
    draw_glass_panel(c, bg, header, 32 * s, tint=TOKENS["GLASS_FILL_MAIN"])
    d.text((header[0] + 34 * s, header[1] + 18 * s), "ЛИДЕРБОРД", fill=TOKENS["TEXT_PRIMARY"], font=font(52 * s, "bold"))
    sub, sf = fit_text_to_width(decade_title or "1-я декада", 30 * s, 17 * s, 960 * s, "medium")
    d.text((header[0] + 34 * s, header[1] + 92 * s), sub, fill=TOKENS["TEXT_SECONDARY"], font=sf)
    draw_glass_pill(c, bg, (header[2] - 310 * s, header[1] + 50 * s, header[2] - 34 * s, header[1] + 112 * s), "Top Heroes")

    avatars = top3_avatars or {}
    top = {2: (56, 242, 486, 538), 1: (450, 206, 1150, 574), 3: (1114, 242, 1544, 538)}
    rank_tints = {1: (120, 150, 255, 48), 2: (110, 200, 255, 44), 3: (130, 160, 255, 44)}
    rank_glow = {1: (120, 130, 255, 96), 2: (95, 205, 255, 70), 3: (120, 150, 255, 62)}
    for rank in (2, 1, 3):
        if len(decade_leaders) < rank:
            continue
        row = decade_leaders[rank - 1]
        x1, y1, x2, y2 = [v * s for v in top[rank]]
        draw_glass_panel(c, bg, (x1, y1, x2, y2), 30 * s, tint=rank_tints[rank], border=TOKENS["GLASS_BORDER_MAIN"], glow=rank_glow[rank])
        draw_glass_pill(c, bg, (x1 + 20 * s, y1 + 18 * s, x1 + 132 * s, y1 + 72 * s), f"#{rank}")
        av_size = (136 if rank == 1 else 110) * s
        av_x = x1 + (x2 - x1 - av_size) // 2
        av_y = y1 + (72 if rank == 1 else 58) * s
        draw_avatar(c, (av_x, av_y, av_x + av_size, av_y + av_size), avatars.get(_safe_i(row.get("telegram_id"))), row.get("name"))
        name, nf = fit_text_to_width(str(row.get("name", "—")), 42 * s if rank == 1 else 34 * s, 20 * s, (x2 - x1) - 60 * s, "semibold")
        nw, nh = measure(d, name, nf)
        ny = av_y + av_size + 18 * s
        d.text((x1 + (x2 - x1 - nw) / 2, ny), name, fill=TOKENS["TEXT_PRIMARY"], font=nf)

        amt = format_money(row.get("total_amount"))
        af = font(56 * s if rank == 1 else 42 * s, "bold")
        aw, ah = measure(d, amt, af)
        ay = ny + nh + 12 * s
        d.text((x1 + (x2 - x1 - aw) / 2, ay), amt, fill=TOKENS["TEXT_PRIMARY"], font=af)

        avg = "—" if float(row.get("total_hours") or 0) <= 0 else f"{_safe_i(row.get('avg_per_hour'))} ₽/ч"
        rr, rc = format_tempo(row.get("run_rate"))
        shifts = str(_safe_i(row.get("shifts_count", row.get("shift_count"))))
        chips = [(f"Avg {avg}", TOKENS["TEXT_SECONDARY"]), (f"Tempo {rr}", rc), (f"Смены {shifts}", TOKENS["TEXT_SECONDARY"])]
        cy1, cy2 = y2 - 54 * s, y2 - 14 * s
        cw = ((x2 - x1) - 42 * s - 2 * 10 * s) // 3
        for i, (txt, col) in enumerate(chips):
            px1 = x1 + 20 * s + i * (cw + 10 * s)
            draw_glass_panel(c, bg, (px1, cy1, px1 + cw, cy2), 16 * s, tint=TOKENS["GLASS_FILL_DARK"])
            t, tf = fit_text_to_width(txt, 18 * s, 12 * s, cw - 12 * s, "medium")
            tw, th = measure(d, t, tf)
            d.text((px1 + (cw - tw) / 2, cy1 + ((cy2 - cy1) - th) / 2 - 1), t, fill=col, font=tf)

    rows = decade_leaders[3:]
    row_h, gap, top_y = 82 * s, 12 * s, 592 * s
    max_rows = max(0, ((H * s - 56 * s - 72 * s) - top_y + gap) // (row_h + gap))
    for idx, row in enumerate(rows[:max_rows], start=4):
        y1 = top_y + (idx - 4) * (row_h + gap)
        y2 = y1 + row_h
        draw_glass_panel(c, bg, (56 * s, y1, (W - 56) * s, y2), 20 * s, tint=TOKENS["GLASS_FILL_DARK"])
        rx1, rx2 = 56 * s, (W - 56) * s
        draw_glass_pill(c, bg, (rx1 + 14 * s, y1 + 16 * s, rx1 + 100 * s, y1 + 64 * s), f"#{idx}")
        draw_avatar(c, (rx1 + 116 * s, y1 + 12 * s, rx1 + 174 * s, y1 + 70 * s), None, row.get("name"))
        name, nf = fit_text_to_width(str(row.get("name", "—")), 30 * s, 15 * s, 430 * s, "medium")
        d.text((rx1 + 194 * s, y1 + 24 * s), name, fill=TOKENS["TEXT_PRIMARY"], font=nf)
        avg = "—" if float(row.get("total_hours") or 0) <= 0 else f"{_safe_i(row.get('avg_per_hour'))} ₽/ч"
        rr, rc = format_tempo(row.get("run_rate"))
        shifts_txt = str(_safe_i(row.get("shifts_count", row.get("shift_count"))))
        d.text((rx1 + 700 * s, y1 + 24 * s), avg, fill=TOKENS["TEXT_SECONDARY"], font=font(24 * s, "regular"))
        d.text((rx1 + 930 * s, y1 + 24 * s), rr, fill=rc, font=font(24 * s, "semibold"))
        d.text((rx1 + 1070 * s, y1 + 24 * s), shifts_txt, fill=TOKENS["TEXT_MUTED"], font=font(24 * s, "regular"))
        amt = format_money(row.get("total_amount"))
        af = font(34 * s, "bold")
        aw, _ = measure(d, amt, af)
        d.text((rx2 - 28 * s - aw, y1 + 20 * s), amt, fill=TOKENS["TEXT_PRIMARY"], font=af)

    total = sum(_safe_i(x.get("total_amount")) for x in decade_leaders)
    foot = (56 * s, 836 * s, (W - 56) * s, 888 * s)
    draw_glass_panel(c, bg, foot, 16 * s, tint=TOKENS["GLASS_FILL_DARK"])
    parts = [f"Участников: {len(decade_leaders)}", f"Общий объём: {format_money(total)}", f"Обновлено: {format_update_dt(updated_at)}"]
    pw = (foot[2] - foot[0]) // 3
    for i, t in enumerate(parts):
        tt, tf = fit_text_to_width(t, 22 * s, 13 * s, pw - 20 * s, "medium")
        d.text((foot[0] + i * pw + 10 * s, foot[1] + 12 * s), tt, fill=TOKENS["TEXT_SECONDARY"], font=tf)

    out = c.resize((W, H), Image.Resampling.LANCZOS)
    bio = BytesIO(); bio.name = "leaderboard.png"; out.convert("RGB").save(bio, format="PNG"); bio.seek(0)
    return bio
