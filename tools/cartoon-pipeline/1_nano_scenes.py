#!/usr/bin/env python3
"""Stage 1 — Nano Banana keyframes.
Reads scenes.json, generates one 9:16 keyframe per scene into $CARTOON_DIR/keyframes/,
attaching every image in $CARTOON_DIR/refs/ for character consistency.
Scenes with an "end_keyframe" prompt also get keyframes/<scene>_end.png (the clip's
last frame for Veo interpolation). Skips images that already exist (resumable).
Scene names as arguments restrict the run to those scenes (default: all)."""
import os, re, sys, json, base64, glob, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("CARTOON_DIR", os.path.join(HERE, "build"))
KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-2.5-flash-image"

cfg = json.load(open(os.path.join(HERE, "scenes.json")))
outdir = os.path.join(BASE, "keyframes")
os.makedirs(outdir, exist_ok=True)
refs = sorted(glob.glob(os.path.join(BASE, "refs", "*.png"))) \
    or sorted(glob.glob(os.path.join(HERE, "refs", "*.png")))
if not refs:
    print(f"warning: no reference images in {BASE}/refs/ or {HERE}/refs/ — characters may drift")

def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()

def gen(name, prompt, extra_refs=()):
    parts = [{"text": prompt}] + [
        {"inlineData": {"mimeType": "image/png", "data": b64(r)}}
        for r in [*refs, *extra_refs]]
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": "9:16"}}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"[{name}] HTTP {e.code}: {e.read().decode()[:300]}"); return False
    for p in resp.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "inlineData" in p:
            data = base64.b64decode(p["inlineData"]["data"])
            tmp = f"{outdir}/{name}.png.part"
            open(tmp, "wb").write(data)
            os.replace(tmp, f"{outdir}/{name}.png")
            print(f"[{name}] saved"); return True
    print(f"[{name}] no image returned"); return False

def main(names=None):
    scenes = cfg["scenes"]
    # scene names become file paths (same guard as 3_compose.sh)
    bad = [s["name"] for s in scenes
           if not re.fullmatch(r"[A-Za-z0-9_-]+", s["name"])]
    if bad:
        sys.exit(f"invalid scene name(s): {bad} (use letters/digits/_/- only)")
    if names:
        unknown = set(names) - {s["name"] for s in scenes}
        if unknown:
            sys.exit(f"unknown scene(s): {sorted(unknown)}")
        scenes = [s for s in scenes if s["name"] in names]
    order = [s["name"] for s in cfg["scenes"]]
    ok = True
    for sc in scenes:
        i = order.index(sc["name"])
        # continuity: seed a start keyframe with the previous scene's end frame,
        # and an end keyframe with its own start frame, when those exist on disk
        prev_end = f"{outdir}/{order[i-1]}_end.png" if i else None
        own_start = f"{outdir}/{sc['name']}.png"
        jobs = [(sc["name"], sc["keyframe"], prev_end)]
        if "end_keyframe" in sc:
            jobs.append((sc["name"] + "_end", sc["end_keyframe"], own_start))
        for fname, prompt, seed in jobs:
            if os.path.exists(f"{outdir}/{fname}.png"):
                print(f"[{fname}] exists, skipping"); continue
            extra = [seed] if seed and os.path.exists(seed) else []
            if not gen(fname, cfg["style_image"] + " " + prompt, extra):
                # don't generate an end frame unseeded by its failed start frame:
                # resume would freeze it that way forever
                ok = False
                break
    return ok

if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1:] or None) else 1)
