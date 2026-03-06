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


def background(width: int, height: int):
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
        ((width // 2 - 160, height // 2 - 160, width + 240, height + 260), "#65AFFF", 40),
        ((width // 6, height // 8, width // 2, height // 2), "#FFD79A", 18),
        ((width // 2, height // 5, width - 40, height // 2 + 80), "#FFB7D5", 16),
    ]
    for box, col, a in glows:
        gd.ellipse(box, fill=_hex(col, a))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(150)))
    return img


def draw_glass_panel(canvas: Image.Image, bg: Image.Image, box: tuple[int, int, int, int], radius: int, tint=(220, 235, 255, 40), border=TOKENS["GLASS_BORDER_SOFT"], glow: tuple[int, int, int, int] | None = None):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    m = rounded_mask((w, h), radius)
    crop = bg.crop(box).filter(ImageFilter.GaussianBlur(24))
    crop = ImageEnhance.Brightness(crop).enhance(1.16)
    canvas.paste(crop, (x1, y1), m)

    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sc = glow or (80, 140, 255, 62)
    ImageDraw.Draw(sh, "RGBA").rounded_rectangle((x1 + 2, y1 + 10, x2 + 2, y2 + 16), radius=radius, fill=sc)
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(24)))

    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=tint, outline=border, width=2)
    d.rounded_rectangle((4, 4, w - 5, max(18, h // 2)), radius=max(8, radius - 8), outline=TOKENS["GLASS_TOP_HIGHLIGHT"], width=1)
    d.line((12, 12, w - 18, 12), fill=(255, 255, 255, 90), width=2)
    d.ellipse((w - 90, 10, w - 10, 50), fill=(255, 255, 255, 18))
    d.polygon([(8, h - 42), (28, h - 36), (18, h - 12)], fill=(255, 180, 120, 18))
    d.polygon([(w - 26, h - 56), (w - 8, h - 40), (w - 38, h - 30)], fill=(120, 190, 255, 20))
    canvas.alpha_composite(card, (x1, y1))


def draw_glass_pill(canvas, bg, box, text, color=TOKENS["TEXT_PRIMARY"], weight="semibold"):
    draw_glass_panel(canvas, bg, box, radius=(box[3] - box[1]) // 2, tint=TOKENS["GLASS_FILL_DARK"])
    d = ImageDraw.Draw(canvas, "RGBA")
    txt, f = fit_text_to_width(text, 34, 18, box[2] - box[0] - 28, weight=weight)
    tw, th = measure(d, txt, f)
    d.text((box[0] + (box[2] - box[0] - tw) / 2, box[1] + (box[3] - box[1] - th) / 2 - 1), txt, fill=color, font=f)


def draw_progress_bar(canvas, box, completion):
    d = ImageDraw.Draw(canvas, "RGBA")
    x1, y1, x2, y2 = box
    h = y2 - y1
    d.rounded_rectangle(box, radius=h // 2, fill=(255, 255, 255, 36), outline=(255, 255, 255, 76), width=2)
    if completion is None:
        return
    p = max(0.0, min(1.0, float(completion)))
    fw = int((x2 - x1 - 6) * p)
    if fw <= 0:
        return
    grad = Image.new("RGBA", (fw, h - 6), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad, "RGBA")
    c1, c2, c3 = _hex("#69E6FF", 245), _hex("#5DB8FF", 245), _hex("#9A84FF", 245)
    for i in range(fw):
        t = i / max(1, fw - 1)
        if t < 0.6:
            k = t / 0.6
            c = tuple(int(c1[j] + (c2[j] - c1[j]) * k) for j in range(4))
        else:
            k = (t - 0.6) / 0.4
            c = tuple(int(c2[j] + (c3[j] - c2[j]) * k) for j in range(4))
        gd.line((i, 0, i, h - 6), fill=c)
    canvas.paste(grad, (x1 + 3, y1 + 3), rounded_mask((fw, h - 6), (h - 6) // 2))


def draw_avatar(canvas, box, avatar, name):
    x1, y1, x2, y2 = box
    size = min(x2 - x1, y2 - y1)
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size, size), fill=255)
    if avatar is None:
        av = Image.new("RGBA", (size, size), _hex("#5C7CFF", 220))
        initials = "".join(p[:1] for p in str(name or "?").split()[:2]).upper() or "?"
        d = ImageDraw.Draw(av, "RGBA")
        f = font(max(26, size // 3), "bold")
        tw, th = measure(d, initials, f)
        d.text(((size - tw) / 2, (size - th) / 2 - 1), initials, fill=TOKENS["TEXT_PRIMARY"], font=f)
    else:
        av = ImageOps.fit(avatar.convert("RGBA"), (size, size), method=Image.Resampling.LANCZOS)
    canvas.paste(av, (x1, y1), m)
    ImageDraw.Draw(canvas, "RGBA").ellipse((x1 - 3, y1 - 3, x1 + size + 3, y1 + size + 3), outline=TOKENS["GLASS_BORDER_MAIN"], width=3)


def render_dashboard_image_bytes(mode: str, payload: dict) -> BytesIO:
    s = SS
    bg = background(W * s, H * s)
    c = bg.copy()
    d = ImageDraw.Draw(c, "RGBA")

    header = (52 * s, 42 * s, (W - 52) * s, 196 * s)
    draw_glass_panel(c, bg, header, 32 * s, tint=TOKENS["GLASS_FILL_MAIN"])
    d.text((header[0] + 34 * s, header[1] + 18 * s), "Дашборд", fill=TOKENS["TEXT_PRIMARY"], font=font(52 * s, "bold"))
    st, sf = fit_text_to_width(payload.get("decade_title", "—"), 31 * s, 18 * s, 970 * s, "medium")
    d.text((header[0] + 34 * s, header[1] + 88 * s), st, fill=TOKENS["TEXT_SECONDARY"], font=sf)
    draw_glass_pill(c, bg, (header[2] - 372 * s, header[1] + 44 * s, header[2] - 34 * s, header[1] + 106 * s), "Смена закрыта" if mode == "closed" else "Смена активна")

    hero = (52 * s, 214 * s, (W - 52) * s, 742 * s)
    draw_glass_panel(c, bg, hero, 36 * s, tint=TOKENS["GLASS_FILL_LIGHT"], glow=(90, 150, 255, 72))
    lx1 = hero[0] + 38 * s
    d.text((lx1, hero[1] + 28 * s), "Главный KPI", fill=TOKENS["TEXT_PRIMARY"], font=font(40 * s, "semibold"))
    earned = payload.get("decade_earned", payload.get("earned", 0))
    goal = payload.get("decade_goal", payload.get("goal", 0))
    d.text((lx1, hero[1] + 100 * s), format_money(earned), fill=TOKENS["TEXT_PRIMARY"], font=font(84 * s, "bold"))
    d.text((lx1, hero[1] + 220 * s), f"из {format_money(goal)}" if int(goal or 0) > 0 else "из —", fill=TOKENS["TEXT_SECONDARY"], font=font(34 * s, "regular"))

    completion = payload.get("completion_percent")
    tempo_text, tempo_color = format_tempo(payload.get("pace_text"))
    delta_text = payload.get("pace_delta_text", "—")
    delta_label = payload.get("plan_deviation_label", "Отклонение от плана")
    accent = (hero[2] - 470 * s, hero[1] + 34 * s, hero[2] - 34 * s, hero[1] + 312 * s)
    draw_glass_panel(c, bg, accent, 30 * s, tint=(110, 175, 255, 46), border=TOKENS["GLASS_BORDER_MAIN"], glow=(110, 138, 255, 84))
    comp_text = "—" if completion is None else f"{int(round(float(completion) * 100))}%"
    d.text((accent[0] + 34 * s, accent[1] + 22 * s), comp_text, fill=TOKENS["TEXT_PRIMARY"], font=font(70 * s, "bold"))
    d.text((accent[0] + 36 * s, accent[1] + 132 * s), "Выполнение", fill=TOKENS["TEXT_SECONDARY"], font=font(30 * s, "semibold"))
    d.text((accent[0] + 36 * s, accent[1] + 180 * s), f"Темп: {tempo_text}", fill=tempo_color, font=font(28 * s, "medium"))
    dc = TOKENS["TEXT_SECONDARY"] if "—" in str(delta_text) else (TOKENS["POSITIVE"] if str(delta_text).startswith("+") else TOKENS["NEGATIVE"])
    dl, dlf = fit_text_to_width(delta_label, 22 * s, 16 * s, accent[2] - accent[0] - 72 * s, "regular")
    d.text((accent[0] + 36 * s, accent[1] + 226 * s), dl, fill=TOKENS["TEXT_MUTED"], font=dlf)
    dt, dtf = fit_text_to_width(str(delta_text), 27 * s, 18 * s, accent[2] - accent[0] - 72 * s, "semibold")
    d.text((accent[0] + 36 * s, accent[1] + 256 * s), dt, fill=dc, font=dtf)

    draw_progress_bar(c, (hero[0] + 38 * s, hero[1] + 318 * s, hero[2] - 38 * s, hero[1] + 360 * s), completion)

    metrics = (payload.get("decade_metrics") or payload.get("metrics") or [])[:6]
    cw = ((hero[2] - hero[0]) - 76 * s - 2 * 16 * s) // 3
    ch = 140 * s
    for i in range(6):
        row, col = divmod(i, 3)
        bx1 = hero[0] + 38 * s + col * (cw + 16 * s)
        by1 = hero[1] + 376 * s + row * (ch + 16 * s)
        draw_glass_panel(c, bg, (bx1, by1, bx1 + cw, by1 + ch), 22 * s, tint=TOKENS["GLASS_FILL_DARK"])
        title, value, clr = (metrics[i] if i < len(metrics) else ("—", "—", TOKENS["TEXT_PRIMARY"]))
        t, tf = fit_text_to_width(str(title), 24 * s, 15 * s, cw - 28 * s, "medium")
        v, vf = fit_text_to_width(str(value), 42 * s, 22 * s, cw - 28 * s, "bold")
        d.text((bx1 + 16 * s, by1 + 16 * s), t, fill=TOKENS["TEXT_MUTED"], font=tf)
        d.text((bx1 + 16 * s, by1 + 64 * s), v, fill=clr, font=vf)

    footer = (52 * s, 770 * s, (W - 52) * s, 858 * s)
    draw_glass_panel(c, bg, footer, 22 * s, tint=TOKENS["GLASS_FILL_DARK"])
    mini = payload.get("mini") or []
    parts = [mini[i] if i < len(mini) else "—" for i in range(3)]
    parts.append(f"Обновлено: {format_update_dt(payload.get('updated_at'))}")
    pw = (footer[2] - footer[0] - 24 * s) // 4
    for i, txt in enumerate(parts):
        tt, tf = fit_text_to_width(str(txt), 25 * s, 14 * s, pw - 16 * s, "medium")
        d.text((footer[0] + 10 * s + i * pw, footer[1] + 26 * s), tt, fill=TOKENS["TEXT_SECONDARY"], font=tf)

    out = c.resize((W, H), Image.Resampling.LANCZOS)
    bio = BytesIO(); bio.name = "dashboard.png"; out.convert("RGB").save(bio, format="PNG"); bio.seek(0)
    return bio


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
