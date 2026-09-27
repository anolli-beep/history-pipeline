"""Assemble the video with ffmpeg: slow pans over images, captions, chapter titles, narration, music."""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, font_path, log, media_duration, run

W, H, FPS = 1920, 1080, 25
MIN_SHOT = 3.5
OUTRO_SECONDS = 6.0

# Pan/zoom patterns, rotated so consecutive shots move differently.
MOVES = [
    ("1+0.10*on/{F}", "iw/2-iw/zoom/2", "ih/2-ih/zoom/2"),            # slow zoom in
    ("1.10-0.10*on/{F}", "iw/2-iw/zoom/2", "ih/2-ih/zoom/2"),         # slow zoom out
    ("1.10", "(iw-iw/zoom)*on/{F}", "ih/2-ih/zoom/2"),                 # pan left to right
    ("1.10", "(iw-iw/zoom)*(1-on/{F})", "ih/2-ih/zoom/2"),             # pan right to left
    ("1+0.08*on/{F}", "iw/2-iw/zoom/2", "(ih-ih/zoom)*0.35"),          # zoom in, upper third
]


def _prep_image(src: Path, dest: Path) -> None:
    """Fit onto a 16:9 canvas: cover-crop when close to 16:9, otherwise blurred background."""
    from PIL import ImageFilter
    img = Image.open(src).convert("RGB")
    cw, ch = 3200, 1800
    ratio = img.width / img.height
    if 1.45 <= ratio <= 2.0:
        scale = max(cw / img.width, ch / img.height)
        img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
        left, top = (img.width - cw) // 2, (img.height - ch) // 2
        img.crop((left, top, left + cw, top + ch)).save(dest, "JPEG", quality=92)
        return
    bg_scale = max(cw / img.width, ch / img.height)
    bg = img.resize((int(img.width * bg_scale) + 1, int(img.height * bg_scale) + 1))
    bg = bg.crop((0, 0, cw, ch)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", bg.size, (10, 10, 12)), 0.45)
    fg_scale = min(cw * 0.92 / img.width, ch * 0.92 / img.height)
    fg = img.resize((int(img.width * fg_scale), int(img.height * fg_scale)), Image.LANCZOS)
    bg.paste(fg, ((cw - fg.width) // 2, (ch - fg.height) // 2))
    bg.save(dest, "JPEG", quality=92)


def _textfile(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    # drawtext textfile paths need ':' and '\' escaped
    return str(path).replace("\\", "/").replace(":", r"\:")


def _segment(img: Path, seconds: float, move: int, out: Path, tmp: Path,
             caption: str = "", chapter: str = "") -> None:
    frames = max(1, round(seconds * FPS))
    z, x, y = (m.format(F=frames) for m in MOVES[move % len(MOVES)])
    vf = [f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}", "format=yuv420p"]
    bold, regular = font_path(True), font_path(False)
    if caption:
        tf = _textfile(tmp / (out.stem + "_cap.txt"), caption)
        vf.append(f"drawtext=fontfile='{regular}':textfile='{tf}':fontsize=30:fontcolor=white@0.92:"
                  f"box=1:boxcolor=black@0.5:boxborderw=14:x=48:y=h-th-54")
    if chapter:
        tf = _textfile(tmp / (out.stem + "_chap.txt"), chapter.upper())
        vf.append(f"drawtext=fontfile='{bold}':textfile='{tf}':fontsize=62:fontcolor=white:"
                  f"box=1:boxcolor=black@0.55:boxborderw=26:x=(w-tw)/2:y=h*0.16:enable='lt(t,4)'")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(img), "-vf", ",".join(vf),
         "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-r", str(FPS), "-an", str(out)])


def _outro_card(cfg: dict, path: Path) -> None:
    img = Image.new("RGB", (3200, 1800), (14, 14, 18))
    d = ImageDraw.Draw(img)
    f1 = ImageFont.truetype(font_path(True), 150)
    f2 = ImageFont.truetype(font_path(False), 72)
    for text, font, y in ((cfg["channel_name"], f1, 700), ("Sources and image credits in the description", f2, 930)):
        w = d.textlength(text, font=font)
        d.text(((3200 - w) / 2, y), text, font=font, fill=(240, 236, 228))
    img.save(path, "JPEG", quality=92)


def _srt_time(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"


def build_srt(script: dict, path: Path) -> None:
    lines, t, n = [], 0.0, 1
    for scene in script["scenes"]:
        speech = scene["duration"] - 0.45
        words = scene["narration"].split()
        chunks = [" ".join(words[i:i + 11]) for i in range(0, len(words), 11)]
        total_chars = sum(len(c) for c in chunks) or 1
        ct = t
        for c in chunks:
            d = speech * len(c) / total_chars
            lines += [str(n), f"{_srt_time(ct)} --> {_srt_time(ct + d)}", c, ""]
            ct += d
            n += 1
        t += scene["duration"]
    path.write_text("\n".join(lines), encoding="utf-8")


def render(cfg: dict, script: dict, work: Path) -> Path:
    segs_dir = work / "segments"
    prep_dir = work / "prepped"
    for d in (segs_dir, prep_dir):
        d.mkdir(parents=True, exist_ok=True)

    segments, move = [], 0
    chapters, t = [], 0.0
    for si, scene in enumerate(script["scenes"]):
        if scene.get("chapter"):
            chapters.append((t, scene["chapter"]))
        shots = scene["shots"][: max(1, int(scene["duration"] // MIN_SHOT))]
        per = scene["duration"] / len(shots)
        for k, shot in enumerate(shots):
            prepped = prep_dir / (Path(shot["path"]).stem + ".jpg")
            if not prepped.exists():
                _prep_image(Path(shot["path"]), prepped)
            seg = segs_dir / f"seg_{si:03d}_{k}.mp4"
            _segment(prepped, per, move, seg, segs_dir, shot.get("caption", ""),
                     scene["chapter"] if (k == 0 and scene.get("chapter") and si > 0) else "")
            segments.append(seg)
            move += 1
        t += scene["duration"]
        log(f"Rendered scene {si + 1}/{len(script['scenes'])}")

    outro_img = prep_dir / "outro.jpg"
    _outro_card(cfg, outro_img)
    outro = segs_dir / "seg_zzz_outro.mp4"
    _segment(outro_img, OUTRO_SECONDS, 0, outro, segs_dir)
    segments.append(outro)

    concat_list = work / "segments.txt"
    concat_list.write_text("".join(f"file '{s.resolve()}'\n" for s in segments))
    silent = work / "video_silent.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(silent)])

    # Narration: each scene padded to its planned duration, then joined.
    inputs, filters = [], []
    for i, scene in enumerate(script["scenes"]):
        inputs += ["-i", scene["audio"]]
        filters.append(f"[{i}:a]aresample=44100,apad=whole_dur={scene['duration']}[a{i}]")
    n = len(script["scenes"])
    total = media_duration(silent)
    filters.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,apad=whole_dur={total}[narr]")
    music = ROOT / "assets" / "music.mp3"
    if music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        filters.append(f"[{n}:a]volume={cfg['music_volume']},atrim=0:{total},"
                       f"afade=t=out:st={max(total - 4, 0)}:d=4[mus]")
        filters.append("[narr][mus]amix=inputs=2:duration=first:normalize=0[aout]")
        out_label = "[aout]"
    else:
        out_label = "[narr]"
    audio = work / "audio.m4a"
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters),
         "-map", out_label, "-c:a", "aac", "-b:a", "192k", "-t", str(total), str(audio)])

    final = work / "final.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(audio),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-shortest",
         "-movflags", "+faststart", str(final)])

    build_srt(script, work / "captions.srt")
    script["chapter_times"] = chapters
    log(f"Video rendered: {media_duration(final)/60:.1f} minutes")
    return final


def fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def chapter_lines(script: dict) -> list[str]:
    """YouTube chapters: first at 0:00, at least 3, each at least 10 seconds apart."""
    out, last = [], -999.0
    for t, name in script.get("chapter_times", []):
        if not out:
            t = 0.0
        if t - last < 10:
            continue
        clean = re.sub(r"\s+", " ", name).strip()
        out.append(f"{fmt_ts(t)} {clean}")
        last = t
    return out if len(out) >= 3 else []
