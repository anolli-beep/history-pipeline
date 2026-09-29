"""Make one history video, ready for you to upload by hand.

    python main.py plan 5                 # pick 5 different topics (used by the batch workflow)
    python main.py produce --job '<json>' # make one planned video
    python main.py produce                # pick a topic and make one video
    python main.py render plans/x.json    # make a video from a plan written in the Claude chat (no API credits)

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
from pathlib import Path

from pipeline import images, packaging, render, voice, writer
from pipeline.common import ROOT, WORK, load_config, load_state, log, next_free_slot, save_state, slugify

OUT = ROOT / "out"


def _when(slot, fmt: str) -> str:
    return f"{slot:{fmt}} (UK time)" if slot else "your next free slot"


def upload_sheet(script, desc, slot, cfg) -> str:
    return f"""UPLOAD DETAILS (copy each part into YouTube Studio)
================================================================

CHANNEL: {cfg['channel_name']}

SUGGESTED PUBLISH TIME: {_when(slot, '%A %d %B %Y, %H:%M')}

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

{script.get('lane')} · {script['narration_seconds']/60:.1f} minutes · suggested publish time **{_when(slot, '%a %d %b, %H:%M')}**

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


def plan(count: int) -> None:
    """Pick `count` different topics and publish slots up front, so videos can be made in parallel."""
    import os
    cfg, state = load_config(), load_state()
    jobs, chosen = [], []
    for i in range(count):
        t = writer.pick_topic(cfg, state, offset=i, also_avoid=chosen)
        chosen.append(t["topic"])
        slot = next_free_slot(cfg, state)
        state["booked_slots"].append(slot.isoformat())
        jobs.append({"n": i + 1, "topic": t["topic"], "angle": t["angle"], "lane": t["lane"],
                     "slot": slot.isoformat()})
    state["used_topics"] += chosen
    state["lane_index"] = state.get("lane_index", 0) + count
    save_state(state)
    payload = json.dumps(jobs, ensure_ascii=False)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"jobs={payload}\n")
    for j in jobs:
        log(f"Video {j['n']}: {j['topic']} ({j['lane']}) -> {j['slot']}")


def produce(job: dict | None = None) -> None:
    cfg, state = load_config(), load_state()
    if job:
        topic = {"topic": job["topic"], "angle": job["angle"], "lane": job["lane"]}
    else:
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

    if job:
        slot = datetime.fromisoformat(job["slot"])
    else:
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
    archive = ROOT / ("new_archive" if job else "archive") / slug
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "brief.json").write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copy(OUT / "UPLOAD.txt", archive / "UPLOAD.txt")
    shutil.copy(OUT / "script.txt", archive / "script.txt")

    if not job:  # planned batch runs record topics and slots in the plan step instead
        state["used_topics"].append(topic["topic"])
        state["lane_index"] = state.get("lane_index", 0) + 1
        state["booked_slots"].append(slot.isoformat())
        save_state(state)
    shutil.rmtree(work, ignore_errors=True)
    log(f"Done: {script['title']} (suggested slot {slot:%a %d %b %H:%M})")


def render_plan(plan_path: str) -> None:
    """Make a video from a plan written in the Claude chat. Uses ElevenLabs and Wikimedia only:
    no Claude API calls, so no Anthropic console credits."""
    cfg = load_config()
    script = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    for key in ("title", "scenes"):
        if key not in script:
            raise SystemExit(f"{plan_path} is missing '{key}'")
    script.setdefault("alt_titles", [])
    script.setdefault("tags", [])
    script.setdefault("thumbnail_text", " ".join(script["title"].split()[:3]))
    script.setdefault("description_summary", "")
    if not script["scenes"][0].get("chapter"):
        script["scenes"][0]["chapter"] = "Introduction"
    script["word_count"] = sum(len(s["narration"].split()) for s in script["scenes"])
    brief = {"sources": script.get("sources", []), "unverified": script.get("unverified", [])}
    slug = Path(plan_path).stem
    work = WORK / slug
    work.mkdir(parents=True, exist_ok=True)
    log(f"Rendering plan: {script['title']} ({script['word_count']} words, {len(script['scenes'])} scenes)")

    voice.narrate(cfg, script, work / "audio")
    img_report = images.resolve_plan_images(cfg, script, work / "images")
    video = render.render(cfg, script, work)
    thumb = packaging.thumbnail(script, work / "thumbnail.jpg")
    desc = packaging.description(cfg, script, brief)

    attention = []
    if img_report["miss_rate"] > 0.35:
        attention.append(f"{int(img_report['miss_rate'] * 100)}% of the planned images couldn't be found, "
                         "so some images repeat. Watch it through first.")
    mins = script["narration_seconds"] / 60
    if not 7.5 <= mins <= 12.5:
        attention.append(f"Narration is {mins:.1f} minutes, outside the 8-12 minute target.")
    attention = " ".join(attention)
    slot = datetime.fromisoformat(script["publish_at"]) if script.get("publish_at") else None

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
    (OUT / "issue.md").write_text(issue_text(script, brief, {}, img_report, slot, attention), encoding="utf-8")
    (OUT / "issue_title.txt").write_text(
        f"{'⚠️ ' if attention else ''}Ready to upload: {script['title']}", encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    log(f"Done: {script['title']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["plan"]:
        plan(max(1, min(5, int(args[1]) if len(args) > 1 and args[1] else 1)))
    elif args[:1] == ["render"] and len(args) > 1:
        render_plan(args[1])
    elif args[:1] == ["produce"]:
        job = json.loads(args[2]) if len(args) > 2 and args[1] == "--job" else None
        produce(job)
    else:
        sys.exit("Usage: python main.py plan <1-5>  |  python main.py produce [--job '<json>']")
