#!/usr/bin/env python3
"""Stage 6 — the SPEAKER gate. Timing alignment (stage 5) can be perfect while the
WRONG character's mouth moves — e.g. Veo animates the listener's shocked-open mouth
through the speaker's line. This gate samples frames across every line's window in
each dubbed clip and asks Gemini vision whose mouth is actually moving.

PASS per line: the scripted speaker's mouth is the moving one and the other
character's mouth is mostly still. Exit 1 on any failure.

Fixes for failures (in order of preference):
  1. Keyframe edit: close the non-speaker's mouth in the scene keyframe
     (targeted Nano Banana edit of the exact frame), re-roll the Veo scene.
  2. Action-prompt direction: "each character's mouth moves ONLY while that
     character is speaking" (see scenes.json s3/s5).
"""
import os, sys, json, base64, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("CARTOON_DIR", os.path.join(HERE, "build"))
KEY = os.environ["GEMINI_API_KEY"]
VISION_MODEL = "gemini-flash-latest"
N_FRAMES = 6

CHARACTER_KEY = ("BOSS = tall, bald with spiky hair tufts on the sides, navy suit, red "
                 "tie. ENG (engineer) = round black glasses, dark side-parted hair, white "
                 "short-sleeve shirt, thin black tie, usually seated.")

def strip_for_line(clip, fs, fe, out):
    """Tile N_FRAMES sampled across [fs, fe] of the clip into one image."""
    from PIL import Image
    tiles = []
    for k in range(N_FRAMES):
        t = fs + (fe - fs) * (k + 0.5) / N_FRAMES
        f = out + f".f{k}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", clip,
                        "-frames:v", "1", f], check=True)
        im = Image.open(f).convert("RGB")
        im.thumbnail((260, 480))
        tiles.append(im)
        os.remove(f)
    W = sum(t_.width for t_ in tiles) + 4 * (N_FRAMES - 1)
    H = max(t_.height for t_ in tiles)
    strip = Image.new("RGB", (W, H), (255, 255, 255))
    x = 0
    for t_ in tiles:
        strip.paste(t_, (x, 0)); x += t_.width + 4
    strip.save(out)
    return out

def judge(strip_path, speaker):
    img = base64.b64encode(open(strip_path, "rb").read()).decode()
    prompt = (f"This is a strip of {N_FRAMES} frames sampled across ONE dialogue line of a "
              f"cartoon. {CHARACTER_KEY}\n"
              f"The scripted speaker for this line is: {speaker.upper()}.\n"
              "A character's mouth is 'moving' if it does sustained TALKING-like open/close "
              "across the frames (open mid-speech in 3+ frames, shape changing). "
              "Small incidental movement — a smile forming, a flinch, lips parting once — "
              "counts as 'still'.\n"
              "Assess BOTH characters. Return exactly one JSON object, nothing else, and do "
              "not use quotation marks inside the notes string: "
              '{"boss_mouth": "moving|still|unclear|offscreen", '
              '"eng_mouth": "moving|still|unclear|offscreen", '
              '"match": true/false (true only if the scripted speaker is the moving one and '
              'the other is mostly still), "notes": "one sentence"}')
    body = {"contents": [{"parts": [{"text": prompt},
                {"inlineData": {"mimeType": "image/png", "data": img}}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{VISION_MODEL}:generateContent?key={KEY}"
    last = None
    for attempt in range(3):
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.load(r)
        text = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
        try:
            # take the first JSON value even if trailing text/objects follow
            obj, _ = json.JSONDecoder().raw_decode(text)
            if isinstance(obj, list):
                obj = obj[0]
            return obj
        except (json.JSONDecodeError, IndexError, KeyError) as ex:
            last = ex
    raise RuntimeError(f"speaker judge returned unparseable JSON 3x: {last}")

def main():
    cfg = json.load(open(os.path.join(HERE, "scenes.json")))
    scenes = cfg["scenes"]
    names = sys.argv[1:]
    if names:
        unknown = set(names) - {s["name"] for s in scenes}
        if unknown:
            sys.exit(f"unknown scene(s): {sorted(unknown)}")
        scenes = [s for s in scenes if s["name"] in names]
    raw = json.load(open(f"{BASE}/windows.json"))
    windows = {k: (v["wins"] if isinstance(v, dict) else v) for k, v in raw.items()}
    tmp = f"{BASE}/tts"
    os.makedirs(tmp, exist_ok=True)
    failures = 0
    print(f"{'scene':<16} ln spk   boss_mouth  eng_mouth   verdict")
    for sc in scenes:
        name = sc["name"]
        clip = f"{BASE}/clips/{name}_dub.mp4"
        if not os.path.exists(clip):
            clip = f"{BASE}/clips/{name}.mp4"
        for i, (who, text) in enumerate([tuple(l) for l in sc["lines"]]):
            fs, fe = windows[name][i]
            strip = strip_for_line(clip, fs, fe, f"{tmp}/_spk_{name}_{i}.png")
            v = judge(strip, who)
            ok = bool(v.get("match"))
            failures += 0 if ok else 1
            print(f"{name:<16} {i}  {who:<5} {v.get('boss_mouth','?'):<11} "
                  f"{v.get('eng_mouth','?'):<11} {'PASS' if ok else 'FAIL'}  {v.get('notes','')[:60]}")
    print(f"\n{'ALL LINES PASS' if failures == 0 else f'{failures} line(s) FAIL'}")
    sys.exit(0 if failures == 0 else 1)

if __name__ == "__main__":
    main()
