"""Make one history video, ready for you to upload by hand.

    python main.py produce

Everything for the upload is written to the `out/` folder:
    video.mp4, thumbnail.jpg, captions.srt, UPLOAD.txt (title, description, tags,
    suggested publish time), pinned_comment.txt (only if needed), script.txt
and a summary for the GitHub "Ready to upload" issue (out/issue.md).
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime

from pipeline import images, packaging, render, voice, writer
from pipeline.common import ROOT, WORK, load_config, load_state, log, next_free_slot, save_state, slugify

OUT = ROOT / "out"


def upload_sheet(script, desc, slot, cfg) -> str:
    return f"""UPLOAD DETAILS (copy each part into YouTube Studio)
================================================================

CHANNEL: {cfg['channel_name']}

SUGGESTED PUBLISH TIME: {slot:%A %d %B %Y, %H:%M} (UK time)

TITLE:
{script['title']}

(Other title options: {' | '.join(script.get('alt_titles', []))})

DESCRIPTION:
{desc}

TAGS (paste into "Tags", under "Show more"):
{', '.join(script.get('tags', []))}

SETTINGS:
- Audience: No, it's not made for kids
- Altered or synthetic content: Yes (AI narration)
- Category: Education
- Subtitles: upload captions.srt (Subtitles > Add language > English > Upload file > With timing)
- Thumbnail: upload thumbnail.jpg
"""


def issue_text(script, brief, check, img_report, slot, attention) -> str:
    unverified = "\n".join(f"- {u.get('claim')} ({u.get('reason')})"
                           for u in brief.get("unverified", [])) or "- none"
    fixes = "\n".join(f"- Scene {i.get('scene')}: \"{i.get('text')}\" → \"{i.get('fix')}\" ({i.get('problem')})"
                      for i in check.get("issues", [])) or "- none"
    head = f"### ⚠️ Needs attention\n{attention}\n\n" if attention else ""
    return f"""{head}**{script['title']}**

{script.get('lane')} · {script['narration_seconds']/60:.1f} minutes · suggested publish time **{slot:%a %d %b, %H:%M}**

### How to upload
1. Scroll to the bottom of the linked run page and download the **video-…** file under *Artifacts* (it's a zip).
2. Unzip it and open **UPLOAD.txt**: it has the title, description, tags and settings to copy in.
3. Follow "Uploading a video" in the README. When it's scheduled, close this issue.

### Worth a look before you upload
Unverified claims from the research (the script was told not to use these):
{unverified}

Fact-check corrections already applied:
{fixes}

Images: {img_report['unique_images']} used; {img_report['missed']} of {img_report['requested']} requested shots had no suitable image.
"""


def produce() -> None:
    cfg, state = load_config(), load_state()
    topic = writer.pick_topic(cfg, state)
    slug = f"{date.today():%Y%m%d}-{slugify(topic['topic'])}"
    work = WORK / slug
    work.mkdir(parents=True, exist_ok=True)

    brief = writer.research(cfg, topic)
    script = writer.write_script(cfg, topic, brief)
    check = writer.fact_check(cfg, script, brief)
    script["lane"] = topic["lane"]
    voice.narrate(cfg, script, work / "audio")
    img_report = images.find_images(cfg, script, work / "images")
    video = render.render(cfg, script, work)
    thumb = packaging.thumbnail(script, work / "thumbnail.jpg")
    desc = packaging.description(cfg, script, brief)

    attention = []
    if check.get("verdict") == "fail":
        attention.append("The fact-checker failed this script. Read the script before uploading.")
    if img_report["miss_rate"] > 0.35:
        attention.append(f"{int(img_report['miss_rate'] * 100)}% of image searches found nothing suitable, "
                         "so some images repeat. Watch it through first.")
    mins = script["narration_seconds"] / 60
    if not 7.5 <= mins <= 12.5:
        attention.append(f"Narration is {mins:.1f} minutes, outside the 8-12 minute target.")
    attention = " ".join(attention)

    slot = next_free_slot(cfg, state)

    # Everything you need for the upload goes in out/
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir()
    shutil.copy(video, OUT / "video.mp4")
    shutil.copy(thumb, OUT / "thumbnail.jpg")
    shutil.copy(work / "captions.srt", OUT / "captions.srt")
    (OUT / "UPLOAD.txt").write_text(upload_sheet(script, desc, slot, cfg), encoding="utf-8")
    if "pinned comment" in desc:
        (OUT / "pinned_comment.txt").write_text(packaging.credits_comment(script), encoding="utf-8")
    (OUT / "script.txt").write_text("\n\n".join(
        (f"## {s['chapter']}\n\n" if s.get("chapter") else "") + s["narration"] for s in script["scenes"]),
        encoding="utf-8")
    (OUT / "issue.md").write_text(issue_text(script, brief, check, img_report, slot, attention), encoding="utf-8")
    (OUT / "issue_title.txt").write_text(
        f"{'⚠️ ' if attention else ''}Ready to upload: {script['title']}", encoding="utf-8")

    # Keep a small text record in the repo
    archive = ROOT / "archive" / slug
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "brief.json").write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copy(OUT / "UPLOAD.txt", archive / "UPLOAD.txt")
    shutil.copy(OUT / "script.txt", archive / "script.txt")

    state["used_topics"].append(topic["topic"])
    state["lane_index"] = state.get("lane_index", 0) + 1
    state["booked_slots"].append(slot.isoformat())
    state["videos"].append({"title": script["title"], "slug": slug, "slot": slot.isoformat(),
                            "created": datetime.now().isoformat(timespec="minutes")})
    save_state(state)
    shutil.rmtree(work, ignore_errors=True)
    log(f"Done: {script['title']} (suggested slot {slot:%a %d %b %H:%M})")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "produce":
        sys.exit("Usage: python main.py produce")
    produce()
