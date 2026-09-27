"""Topic selection, research brief and script writing (Prompts 2-5)."""
from __future__ import annotations

import json
from difflib import SequenceMatcher

from .common import ask_claude, extract_json, log

STYLE_RULES = """
Style rules for every script:
- British English spelling, calm and confident documentary narrator, plain words.
- Cold open: a specific date, place and person in the first 2-3 sentences. No "welcome back",
  no "in today's video", no "let's dive in", no channel name.
- Never use em dashes. No rhetorical questions as transitions.
- Sentences under 22 words so the AI voice sounds natural.
- Only state facts that appear as VERIFIED in the research brief. Where historians disagree,
  say so ("most historians think", "accounts differ"). Never invent quotes, dialogue,
  thoughts or numbers. Direct quotes only if the brief has them with a source.
- No graphic gore. Describe violence and atrocities soberly and without sensationalism.
- Don't draw parallels with present-day politicians or parties.
- End with why the story still matters, then one line: "Sources and image credits are in
  the description."
"""


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def pick_topic(cfg: dict, state: dict) -> dict:
    lanes = cfg["lanes"]
    lane = lanes[state.get("lane_index", 0) % len(lanes)]
    used = state.get("used_topics", [])[-400:]
    system = "You are the head of research for a history documentary YouTube channel."
    prompt = f"""Suggest 10 video topics for the lane "{lane['name']}" ({lane['brief']}).

Requirements for each topic:
- Enough documented evidence for an accurate 10-minute video.
- Plenty of public-domain or openly licensed images likely on Wikimedia Commons
  (paintings, engravings, maps, old photographs, artefacts, places).
- A clear story with a turning point, and a reason modern viewers would click.
- Proven search interest (a well-known event or person, or a surprising angle on one).
- Vary eras and regions; avoid anything already covered below.

Already covered (don't repeat or closely overlap):
{json.dumps(used, ensure_ascii=False)}

Return only:
<json>{{"topics": [{{"topic": "...", "angle": "one sentence on the story and hook",
"era": "...", "region": "...", "image_availability": "high|medium|low"}}]}}</json>"""
    data = extract_json(ask_claude(cfg, system, prompt, max_tokens=4000))
    for t in data["topics"]:
        if t.get("image_availability") == "low":
            continue
        if all(_similar(t["topic"], u) < 0.75 for u in used):
            t["lane"] = lane["name"]
            log(f"Topic: {t['topic']} ({lane['name']})")
            return t
    raise RuntimeError("Claude only suggested topics we've already covered")


def research(cfg: dict, topic: dict) -> dict:
    system = "You are a meticulous historical researcher. Accuracy beats drama."
    prompt = f"""Research this topic for a documentary script and build a fact brief.
Topic: {topic['topic']}
Angle: {topic['angle']}

Use web search. Prefer academic sources, museums, national archives, encyclopaedias
(Britannica, national biography dictionaries) and reputable history publishers over
blogs or content farms.
- Verify every date, name, place, number and quote against at least 2 independent sources.
- Mark anything with only one source, or where sources conflict, as UNVERIFIED and explain.
- Note where historians genuinely disagree.
- List the 6-8 key moments in chronological order.

Return only:
<json>{{
 "summary": "3-4 sentence overview",
 "facts": [{{"claim": "...", "date": "...", "sources": ["url", "url"], "status": "VERIFIED"}}],
 "unverified": [{{"claim": "...", "reason": "..."}}],
 "debates": ["..."],
 "key_moments": [{{"date": "...", "moment": "...", "sources": ["url"]}}],
 "sources": [{{"title": "...", "url": "..."}}]
}}</json>"""
    brief = extract_json(ask_claude(cfg, system, prompt, web_search=15, max_tokens=16000))
    log(f"Research: {len(brief.get('facts', []))} verified facts, "
        f"{len(brief.get('unverified', []))} unverified")
    return brief


def _word_count(script: dict) -> int:
    return sum(len(s["narration"].split()) for s in script["scenes"])


def write_script(cfg: dict, topic: dict, brief: dict) -> dict:
    lo, hi = cfg["script_words_min"], cfg["script_words_max"]
    system = "You write documentary narration for a faceless history YouTube channel." + STYLE_RULES
    prompt = f"""Write the narration for a video on: {topic['topic']}
Angle: {topic['angle']}

Research brief (the ONLY facts you may use):
{json.dumps(brief, ensure_ascii=False)}

Structure:
- {lo}-{hi} words in total (8-12 minutes at 150 words per minute).
- 22-32 scenes of 40-75 words each. Each scene is one continuous thought.
- 6-9 chapters. Put a short chapter title on the FIRST scene of each chapter only
  (null on other scenes). The first scene's chapter is "Introduction" or similar.
- A turning point or reveal at roughly 70-75% of the runtime.
- For each scene give 2-4 image searches for Wikimedia Commons, each naming a concrete,
  real, depictable subject that matches what's being said at that moment: a named painting,
  a portrait of a named person, a specific building, an artefact, a period map of a region,
  a contemporary engraving or photograph. Avoid abstract searches ("betrayal", "war").
  Make the "subject" field a plain-English description of what the image must show.

Also write packaging:
- title: under 70 characters, curiosity-driven but honest (no clickbait the video doesn't pay off)
- alt_titles: 3 alternatives
- thumbnail_text: 2-4 words, uppercase
- description_summary: 2-3 sentences
- tags: 10-15 search tags

Return only:
<json>{{"title": "...", "alt_titles": ["..."], "thumbnail_text": "...",
"description_summary": "...", "tags": ["..."],
"scenes": [{{"chapter": "Introduction", "narration": "...",
  "images": [{{"query": "...", "subject": "..."}}]}}]}}</json>"""
    script = extract_json(ask_claude(cfg, system, prompt, max_tokens=24000))
    words = _word_count(script)
    if not lo <= words <= hi:
        log(f"Script is {words} words; asking for a revision to {lo}-{hi}")
        fix = f"""This script is {words} words. Revise it to {lo}-{hi} words by
{'expanding scenes with more verified detail from the brief' if words < lo else 'tightening'}.
Keep the same JSON shape and all rules.
{json.dumps(script, ensure_ascii=False)}
Brief: {json.dumps(brief, ensure_ascii=False)}"""
        script = extract_json(ask_claude(cfg, system, fix, max_tokens=24000))
        words = _word_count(script)
    script["word_count"] = words
    if not script["scenes"][0].get("chapter"):
        script["scenes"][0]["chapter"] = "Introduction"
    log(f"Script: {words} words, {len(script['scenes'])} scenes")
    return script


def fact_check(cfg: dict, script: dict, brief: dict) -> dict:
    """Second pass: a separate call checks the script against the brief."""
    system = "You are a strict fact-checker for a history channel."
    narration = "\n".join(f"[{i}] {s['narration']}" for i, s in enumerate(script["scenes"]))
    prompt = f"""Check every factual statement in this narration against the research brief.
Flag any statement that is not supported by a VERIFIED fact, is stated more confidently than
the evidence allows, or includes an invented quote, number or detail.

Brief: {json.dumps(brief, ensure_ascii=False)}

Narration:
{narration}

Return only:
<json>{{"issues": [{{"scene": 0, "text": "...", "problem": "...", "fix": "corrected sentence"}}],
"verdict": "pass|fixable|fail"}}</json>"""
    result = extract_json(ask_claude(cfg, system, prompt, max_tokens=8000))
    for issue in result.get("issues", []):
        i = issue.get("scene")
        if isinstance(i, int) and 0 <= i < len(script["scenes"]) and issue.get("fix"):
            s = script["scenes"][i]
            if issue["text"] in s["narration"]:
                s["narration"] = s["narration"].replace(issue["text"], issue["fix"])
    log(f"Fact check: {result.get('verdict')} with {len(result.get('issues', []))} issues")
    return result
