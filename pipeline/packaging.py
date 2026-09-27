"""Thumbnail and YouTube description."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import font_path
from .render import chapter_lines

DESC_LIMIT = 4900


def thumbnail(script: dict, out: Path) -> Path:
    """1280x720: the strongest image, darkened on the left, with 2-4 big words."""
    hero = script["scenes"][0]["shots"][0]["path"]
    img = Image.open(hero).convert("RGB")
    scale = max(1280 / img.width, 720 / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    left, top = (img.width - 1280) // 2, (img.height - 720) // 2
    img = img.crop((left, top, left + 1280, top + 720))
    shade = Image.linear_gradient("L").rotate(90).resize((1280, 720))
    img = Image.composite(Image.new("RGB", img.size, (8, 8, 10)), img, shade.point(lambda v: int((255 - v) * 0.85)))
    d = ImageDraw.Draw(img)
    words = script.get("thumbnail_text", script["title"]).upper().split()
    lines, cur = [], ""
    for w in words:
        if len(cur + " " + w) > 11 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    size = 118 if len(lines) <= 2 else 96
    font = ImageFont.truetype(font_path(True), size)
    y = (720 - len(lines) * (size + 14)) // 2
    for line in lines[:4]:
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).text((62, y + 6), line, font=font, fill=(0, 0, 0, 200))
        img.paste(shadow.filter(ImageFilter.GaussianBlur(6)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(6)))
        d.text((56, y), line, font=font, fill=(250, 214, 120))
        y += size + 14
    img.save(out, "JPEG", quality=90)
    return out


def description(cfg: dict, script: dict, brief: dict) -> str:
    parts = [script["description_summary"].strip(), ""]
    ch = chapter_lines(script)
    if ch:
        parts += ["CHAPTERS", *ch, ""]
    srcs = brief.get("sources", [])[:10]
    if srcs:
        parts.append("SOURCES")
        parts += [f"{s.get('title', 'Source')}: {s.get('url', '')}" for s in srcs]
        parts.append("")
    tail = ["Some details of this history are debated by historians; where accounts differ, "
            "the video says so. Spotted an error? Leave a comment with a source.",
            "",
            f"Narration is AI-generated. Research, script checks and editing by {cfg['channel_name']}."]
    credits = script.get("image_credits", [])

    def credit_block(short: bool) -> list[str]:
        if not credits:
            return []
        lines = ["IMAGE CREDITS (Wikimedia Commons)"]
        for c in credits:
            if short:
                lines.append(f"{c['title'][:60]} ({c['licence']})")
            else:
                lines.append(f"{c['title'][:80]} by {c['artist'][:50]}, {c['licence']}: {c['page']}")
        return lines + [""]

    for short in (False, True):
        text = "\n".join(parts + credit_block(short) + tail)
        if len(text) <= DESC_LIMIT:
            return text
    # Still too long: keep as many credits as fit and point to the list.
    base = "\n".join(parts + tail)
    budget = DESC_LIMIT - len(base) - 120
    lines, used = ["IMAGE CREDITS (Wikimedia Commons, shortened)"], 0
    for c in credits:
        s = f"{c['title'][:50]} ({c['licence']})"
        if used + len(s) + 1 > budget:
            break
        lines.append(s)
        used += len(s) + 1
    return "\n".join(parts + lines + ["Full credits in the pinned comment.", ""] + tail)


def credits_comment(script: dict) -> str:
    lines = ["Image credits (Wikimedia Commons):"]
    for c in script.get("image_credits", []):
        lines.append(f"• {c['title'][:70]} by {c['artist'][:40]}, {c['licence']}: {c['page']}")
    return "\n".join(lines)[:9500]
