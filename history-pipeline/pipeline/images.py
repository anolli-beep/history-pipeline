"""Find accurate, openly licensed images on Wikimedia Commons and check them with Claude."""
from __future__ import annotations

import base64
import html
import io
import re
import time
from pathlib import Path

import requests
from PIL import Image

from .common import ask_claude, extract_json, log

COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "HistoryChannelPipeline/1.0 (personal YouTube channel; contact via GitHub)"}

SKIP_WORDS = ("logo", "icon", "flag of", "coat of arms", "signature", "blank map", "stamp of")


def _strip_html(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def licence_ok(cfg: dict, licence: str) -> bool:
    lic = licence.lower().strip()
    if not lic:
        return False
    if "sa" in re.split(r"[-\s]", lic) or "share" in lic:
        return bool(cfg.get("allow_share_alike"))
    if "nc" in re.split(r"[-\s]", lic) or "nd" in re.split(r"[-\s]", lic):
        return False
    if lic.startswith("pd") or "public domain" in lic or "no restrictions" in lic:
        return True
    return any(lic.startswith(a) for a in cfg["allowed_licences"])


def search_commons(cfg: dict, query: str, limit: int = 12) -> list[dict]:
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 2560,
    }
    for attempt in range(4):
        try:
            r = requests.get(COMMONS, params=params, headers=UA, timeout=40)
            r.raise_for_status()
            break
        except requests.RequestException as e:
            log(f"Commons search failed ({e}); retrying")
            time.sleep(5 * (attempt + 1))
    else:
        return []
    pages = sorted((r.json().get("query", {}).get("pages", {}) or {}).values(),
                   key=lambda p: p.get("index", 99))
    out = []
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        title = p.get("title", "").replace("File:", "")
        if info.get("mime") not in ("image/jpeg", "image/png", "image/tiff", "image/webp"):
            continue
        if info.get("width", 0) < cfg["min_image_width"]:
            continue
        if any(w in title.lower() for w in SKIP_WORDS):
            continue
        if not licence_ok(cfg, lic):
            continue
        out.append({
            "title": title,
            "url": info.get("thumburl") or info.get("url"),
            "page": info.get("descriptionurl"),
            "licence": lic,
            "artist": _strip_html(meta.get("Artist", {}).get("value", ""))[:120] or "Unknown",
            "description": _strip_html(meta.get("ImageDescription", {}).get("value", ""))[:400],
            "date": _strip_html(meta.get("DateTimeOriginal", {}).get("value", ""))[:60],
        })
    return out


def _download(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, headers=UA, timeout=90)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        if img.width < 800:
            return False
        img.save(dest, "JPEG", quality=92)
        return True
    except Exception as e:  # noqa: BLE001
        log(f"Download failed: {e}")
        return False


def _b64_preview(path: Path) -> str:
    img = Image.open(path)
    img.thumbnail((900, 900))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def judge(cfg: dict, subject: str, narration: str, candidates: list[tuple[dict, Path]]) -> tuple[int, int, str]:
    """Ask Claude which candidate best and accurately shows the subject. Returns (index, score, caption)."""
    content = []
    for i, (c, path) in enumerate(candidates):
        content.append({"type": "text", "text": f"Candidate {i}: Commons title '{c['title']}'. "
                                                f"Description: {c['description'] or 'none'}. Date: {c['date'] or 'unknown'}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": _b64_preview(path)}})
    content.append({"type": "text", "text": f"""The narrator says: "{narration}"
The image on screen must show: {subject}

Pick the candidate that most ACCURATELY shows this subject. Reject images of the wrong person,
place, event or period, modern fantasy art presented as history, heavily watermarked images,
text-heavy scans, and anything graphic or gory. Historical paintings made later are acceptable
if they depict the right subject; the caption should then say so (e.g. "painted 1850").

Score 0-10 for accuracy and visual quality. Write a short on-screen caption (max 70 characters)
that honestly says what the image is.

Return only: <json>{{"best": 0, "score": 0, "caption": "...", "reason": "..."}}</json>"""})
    data = extract_json(ask_claude(cfg, "You are a picture researcher for a history documentary.",
                                   content, max_tokens=800,
                                   model=cfg.get("claude_image_model")))
    return int(data.get("best", -1)), int(data.get("score", 0)), data.get("caption", "")[:80]


def find_images(cfg: dict, script: dict, out_dir: Path) -> dict:
    """Attach accepted images to every scene. Returns a report for the review issue."""
    out_dir.mkdir(parents=True, exist_ok=True)
    used_titles: set[str] = set()
    credits: dict[str, dict] = {}
    misses = 0
    n = 0
    for si, scene in enumerate(script["scenes"]):
        scene["shots"] = []
        for qi, want in enumerate(scene.get("images", [])):
            n += 1
            cands = [c for c in search_commons(cfg, want["query"]) if c["title"] not in used_titles][:4]
            local = []
            for ci, c in enumerate(cands):
                dest = out_dir / f"s{si:03d}_{qi}_{ci}.jpg"
                if dest.exists() or _download(c["url"], dest):
                    local.append((c, dest))
            if not local:
                misses += 1
                continue
            best, score, caption = judge(cfg, want["subject"], scene["narration"], local)
            if 0 <= best < len(local) and score >= cfg["image_relevance_threshold"]:
                c, path = local[best]
                used_titles.add(c["title"])
                credits[c["title"]] = c
                scene["shots"].append({"path": str(path), "caption": caption, "title": c["title"]})
            else:
                misses += 1
        log(f"Scene {si + 1}/{len(script['scenes'])}: {len(scene['shots'])} images")

    # Fill gaps: a scene with no images borrows the nearest previous scene's shots.
    last = None
    for scene in script["scenes"]:
        if scene["shots"]:
            last = scene["shots"]
        elif last:
            scene["shots"] = [dict(s, caption="") for s in last[-1:]]
    first = next((s["shots"] for s in script["scenes"] if s["shots"]), None)
    if not first:
        raise RuntimeError("No usable images found for this topic")
    for scene in script["scenes"]:
        if not scene["shots"]:
            scene["shots"] = [dict(first[0], caption="")]

    script["image_credits"] = list(credits.values())
    report = {"requested": n, "missed": misses,
              "miss_rate": round(misses / max(n, 1), 2), "unique_images": len(credits)}
    log(f"Images: {report}")
    return report
