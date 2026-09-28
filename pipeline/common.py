"""Shared helpers: config, state, logging, Claude calls."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "state" / "state.json"
WORK = ROOT / "work"


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- state ----
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"used_topics": [], "lane_index": 0, "videos": [], "booked_slots": []}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def next_free_slot(cfg: dict, state: dict, min_lead_hours: float = 2.0) -> datetime:
    """Next publish slot (timezone-aware) that isn't already booked."""
    tz = ZoneInfo(cfg["timezone"])
    now = datetime.now(tz) + timedelta(hours=min_lead_hours)
    booked = set(state.get("booked_slots", []))
    day = now.date()
    for _ in range(400):
        for t in sorted(cfg["publish_times"]):
            hh, mm = (int(x) for x in t.split(":"))
            slot = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
            if slot > now and slot.isoformat() not in booked:
                return slot
        day += timedelta(days=1)
    raise RuntimeError("No free publish slot found")


# --------------------------------------------------------------- claude ----
_client = None


def claude():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def ask_claude(cfg: dict, system: str, user_content, *, web_search: int = 0,
               max_tokens: int = 16000, model: str | None = None) -> str:
    """Send one request (optionally with web search) and return the final text."""
    tools = []
    if web_search:
        tools.append({"type": "web_search_20250305", "name": "web_search", "max_uses": web_search})
    import anthropic
    messages = [{"role": "user", "content": user_content}]
    for attempt in range(6):
        try:
            kwargs = dict(model=model or cfg["claude_model"], max_tokens=max_tokens,
                          system=system, messages=messages)
            if tools:
                kwargs["tools"] = tools
            # Streaming is required for long responses (big scripts).
            with claude().messages.stream(**kwargs) as stream:
                resp = stream.get_final_message()
        except (anthropic.RateLimitError, anthropic.InternalServerError,
                anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
            wait = 20 * (attempt + 1)
            log(f"Claude busy ({e}); retrying in {wait}s")
            time.sleep(wait)
            continue
        # Anything else (bad key, no credit, wrong model name) stops straight away with a clear error.
        if resp.stop_reason == "pause_turn":
            # long web-search turns: hand the partial turn back and continue
            messages = [messages[0], {"role": "assistant", "content": resp.content}]
            continue
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    raise RuntimeError("Claude request failed repeatedly")


def extract_json(text: str):
    """Pull the JSON object out of <json>...</json> (or the first {...} block)."""
    m = re.search(r"<json>(.*?)</json>", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):]
    return json.loads(raw)


# ---------------------------------------------------------------- media ----
def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd[:6])}...\n{r.stderr[-2000:]}")


def media_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def font_path(bold: bool = True) -> str:
    for p in ([ROOT / "assets" / "font-bold.ttf"] if bold else [ROOT / "assets" / "font.ttf"]) + [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]:
        if Path(p).exists():
            return str(p)
    raise FileNotFoundError("No font found: add assets/font-bold.ttf")
