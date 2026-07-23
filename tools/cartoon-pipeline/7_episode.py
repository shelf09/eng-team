#!/usr/bin/env python3
"""Stage 7 — episode writer.
Generates a NEW episode of the corporate-satire cartoon: Gemini writes only the
"scenes" array (dialogue + keyframe/end_keyframe prompts); the locked visual
style, cast voices, and tts config are copied verbatim from the current
scenes.json so every episode looks and sounds like the same show.

Genre: satire / dry deadpan humor about the corporate world constantly making
stupid decisions. The overconfident boss announces the decision; the deadpan
engineer absorbs it; the last scene lands the punchline.

Usage: python3 7_episode.py [topic words ...]
  no topic  -> the model invents a fresh stupid-corporate-decision premise
Output: episodes/<slug>.json, also activated as scenes.json (the previous one
is tracked by git). Validated before anything is written; one re-roll on a
bad generation, then a hard fail."""
import json, os, re, sys, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ["GEMINI_API_KEY"]
MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-pro-latest")
NAME_RE = r"[A-Za-z0-9_-]+"
MAX_WORDS = 26  # spoken words per scene that still fit an 8s clip

BRIEF = """You write episodes of a 2D-cartoon office-comedy short. Fixed cast:
BOSS (bald, two spiky hair tufts, navy suit, red tie) — smug, booming,
overconfident, announces terrible decisions with total pride. ENGINEER (round
black glasses, white shirt, thin black tie) — flat, tired, deadpan, punctures
the decision with dry one-liners.

GENRE: satire and dry humor about the corporate world constantly making stupid
decisions (RTO mandates with no desks, AI replacing the team that built the AI,
layoffs to fund retention bonuses, agile with fourteen standups...). The boss
proposes/announces; the engineer deadpans; scene 5 lands the punchline. Funny
beats clever; specific beats generic; understatement beats shouting.

Return STRICT JSON only: {"slug": "<short_snake_case_episode_slug>",
"scenes": [exactly 5 scene objects]} — no markdown, no commentary.

Each scene object:
- "name": "s<N>_<word>" (letters/digits/_/- only, N = 1..5 in order)
- "keyframe": image prompt for the scene's FIRST frame. Describe both
  characters' poses/expressions and the shot. Always include: the SAME
  blue-gray glass-walled office (glass panels, blue code monitor, potted
  plant); "The background office must contain NO other people"; "ABSOLUTELY
  NO text anywhere" (unless the scene needs one short written prop, then allow
  exactly that text and nothing else).
- "end_keyframe": image prompt for the scene's LAST frame — the pose the scene
  ends on after the dialogue. Must include: "BOTH MOUTHS FULLY CLOSED. Same
  office, same lighting, same camera framing as the start frame. ABSOLUTELY NO
  text anywhere." (end frames leak invented title cards without this, and the
  leak spreads to the next scene through continuity seeding)
- "action": the animation prompt. Embed every spoken line VERBATIM in double
  quotes with its speaker (e.g.: The boss beams: "..." The engineer replies
  flatly: "...") and state that each character's mouth moves ONLY while that
  character is speaking.
- "lines": [["boss"|"eng", "<exact spoken text>"], ...] in speaking order.
- optional "delivery": a pacing hint ONLY if the scene is rapid-fire.

Hard limits: at most 26 spoken words per scene total (it must fit 8 seconds);
2-3 lines per scene; every line's text appears verbatim inside "action"."""


def jreq(prompt):
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "temperature": 1.0}}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{MODEL}:generateContent?key={KEY}")
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.load(r)
    return resp["candidates"][0]["content"]["parts"][0]["text"]


def parse_episode(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


def normalize(s):
    return (s.replace("“", '"').replace("”", '"')
             .replace("‘", "'").replace("’", "'"))


def validate(ep):
    errs = []
    if not (isinstance(ep, dict) and re.fullmatch(NAME_RE, str(ep.get("slug", "")))):
        errs.append("bad or missing slug")
    scenes = ep.get("scenes") if isinstance(ep, dict) else None
    if not (isinstance(scenes, list) and len(scenes) == 5):
        return errs + ["scenes must be a list of exactly 5"]
    seen = set()
    for i, sc in enumerate(scenes):
        where = f"scene {i+1}"
        name = sc.get("name", "")
        if not re.fullmatch(NAME_RE, name):
            errs.append(f"{where}: invalid name {name!r}")
        if name in seen:
            errs.append(f"{where}: duplicate name {name!r}")
        seen.add(name)
        for field in ("keyframe", "end_keyframe", "action"):
            if not (isinstance(sc.get(field), str) and sc[field].strip()):
                errs.append(f"{where}: missing {field}")
        lines = sc.get("lines")
        if not (isinstance(lines, list) and lines):
            errs.append(f"{where}: missing lines")
            continue
        action = normalize(sc.get("action", ""))
        words = 0
        for line in lines:
            if not (isinstance(line, list) and len(line) == 2
                    and line[0] in ("boss", "eng")):
                errs.append(f"{where}: bad line entry {line!r}")
                continue
            words += len(line[1].split())
            if normalize(line[1]).strip() not in action:
                errs.append(f"{where}: line not verbatim in action: {line[1]!r}")
        if words > MAX_WORDS:
            errs.append(f"{where}: {words} spoken words (max {MAX_WORDS})")
    return errs


def main(argv=None):
    topic = " ".join(argv or [])
    prompt = BRIEF + "\n\nEpisode premise: " + (
        topic if topic else "invent a fresh stupid corporate decision "
        "(one not listed above) and build the episode around it.")
    ep = None
    for attempt in range(2):
        try:
            ep = parse_episode(jreq(prompt))
        except Exception as e:
            errs = [f"unparseable generation: {e}"]
        else:
            errs = validate(ep)
        if not errs:
            break
        print(f"attempt {attempt+1} rejected:", *errs, sep="\n  ", flush=True)
        ep = None
    if ep is None:
        sys.exit("episode generation failed twice — try a different topic")

    seed = json.load(open(os.path.join(HERE, "scenes.json")))
    full = {"episode": ep["slug"],
            "style_image": seed["style_image"], "style_video": seed["style_video"],
            "voices": seed["voices"], "scenes": ep["scenes"], "tts": seed["tts"]}
    epdir = os.path.join(HERE, "episodes")
    os.makedirs(epdir, exist_ok=True)
    path = os.path.join(epdir, f"{ep['slug']}.json")
    json.dump(full, open(path, "w"), indent=2)
    json.dump(full, open(os.path.join(HERE, "scenes.json"), "w"), indent=2)
    print(f"episode saved to {path} and activated as scenes.json", flush=True)
    for sc in ep["scenes"]:
        print(f"[{sc['name']}]")
        for who, text in sc["lines"]:
            print(f"  {who:4}: {text}")
    print("next: python3 0_chain.py  (renders into its own builds/<date>_"
          f"{ep['slug']} run dir)", flush=True)
    return path


if __name__ == "__main__":
    main(sys.argv[1:])
