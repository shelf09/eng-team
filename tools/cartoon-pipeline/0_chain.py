#!/usr/bin/env python3
"""Stage 0 — the per-scene chain: keyframes -> Veo clip -> optional HeyGen
lip-sync, one scene at a time, stopping at the first failure so a bad scene
costs one clip, not the batch. Rerunning resumes: completed work is skipped by
the stages' own exists-on-disk checks.

Each episode renders into its own dated run folder next to its deliverables:
$CARTOON_DIR if set, else <repo>/videos/<episode>/build-<YYYYMMDD>/ (the
newest existing build-* for the episode is reused so reruns resume instead
of re-spending).

Usage: python3 0_chain.py [--heygen] [scene ...]
  --heygen  after each clip, re-animate its lips with HeyGen against the
            scene's dubbed audio (clips/<scene>_dub.mp4) when present, else the
            clip's own audio. Requires HEYGEN_API_KEY; the flag is your consent
            to upload the clip + audio to HeyGen. Output: clips/<scene>_heygen.mp4
            (3_compose.sh prefers these; delete one to re-roll it).
Reuses the hardened HeyGen client in .claude/skills/clone-video-creator/
video-gen/scripts/heygen_lipsync.py (override path via $HEYGEN_LIPSYNC)."""
import argparse, glob, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("CARTOON_DIR", os.path.join(HERE, "build"))
REPO = os.path.dirname(os.path.dirname(HERE))
VIDEOS = os.path.join(REPO, "videos")
HEYGEN_SCRIPT = os.environ.get("HEYGEN_LIPSYNC", os.path.join(
    REPO, ".claude/skills/clone-video-creator/video-gen/scripts/heygen_lipsync.py"))

cfg = json.load(open(os.path.join(HERE, "scenes.json")))

def resolve_base():
    """$CARTOON_DIR wins; else the newest videos/<slug>/build-* run dir; else a
    new dated one — new episode or new day means a new folder, reruns resume."""
    if os.environ.get("CARTOON_DIR"):
        return os.environ["CARTOON_DIR"]
    slug = cfg.get("episode", "episode")
    prior = sorted(glob.glob(os.path.join(VIDEOS, slug, "build-*")))
    if prior:
        return prior[-1]
    return os.path.join(VIDEOS, slug, "build-" + time.strftime("%Y%m%d"))

EXTRA_ENV = {}

def run(argv, stage, scene):
    r = subprocess.run(argv, env=dict(os.environ, CARTOON_DIR=BASE, **EXTRA_ENV))
    if r.returncode != 0:
        sys.exit(f"CHAIN STOPPED at {scene} / {stage} (exit {r.returncode})")

def heygen_scene(name):
    out = f"{BASE}/clips/{name}_heygen.mp4"
    if os.path.exists(out):
        print(f"[{name}] heygen exists, skipping", flush=True); return
    clip = f"{BASE}/clips/{name}.mp4"
    dub = f"{BASE}/clips/{name}_dub.mp4"
    src = dub if os.path.exists(dub) else clip
    os.makedirs(f"{BASE}/heygen", exist_ok=True)
    wav = f"{BASE}/heygen/{name}.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn",
         "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1", wav],
        "audio extract", name)
    run([sys.executable, HEYGEN_SCRIPT, "--video", clip, "--audio", wav,
         "--out", out, "--confirm-upload"], "heygen lipsync", name)
    if not os.path.exists(out):
        sys.exit(f"CHAIN STOPPED at {name} / heygen lipsync (no output produced)")

def main(argv=None):
    ap = argparse.ArgumentParser(description="per-scene keyframes->Veo->HeyGen chain")
    ap.add_argument("--heygen", action="store_true",
                    help="lip-sync each clip with HeyGen (uploads clip + audio)")
    ap.add_argument("--hq", action="store_true",
                    help="render with veo-3.1-fast (2x cost; default is lite)")
    ap.add_argument("scenes", nargs="*", help="scene names (default: all)")
    args = ap.parse_args(argv)

    if args.hq:
        EXTRA_ENV["VEO_MODEL"] = "veo-3.1-fast-generate-preview"

    global BASE
    BASE = resolve_base()
    print(f"run dir: {BASE}", flush=True)

    # scene names become file paths and upload sources (same guard as 3_compose.sh)
    bad = [s["name"] for s in cfg["scenes"]
           if not re.fullmatch(r"[A-Za-z0-9_-]+", s["name"])]
    if bad:
        sys.exit(f"invalid scene name(s): {bad} (use letters/digits/_/- only)")

    names = args.scenes or [s["name"] for s in cfg["scenes"]]
    unknown = set(names) - {s["name"] for s in cfg["scenes"]}
    if unknown:
        sys.exit(f"unknown scene(s): {sorted(unknown)}")

    heygen = args.heygen
    if heygen and not os.environ.get("HEYGEN_API_KEY"):
        print("HEYGEN_API_KEY not set — skipping the HeyGen step this run", flush=True)
        heygen = False

    for name in names:
        print(f"=== {name} ===", flush=True)
        run([sys.executable, os.path.join(HERE, "1_nano_scenes.py"), name],
            "keyframes", name)
        run([sys.executable, os.path.join(HERE, "2_veo_scenes.py"), name],
            "veo", name)
        if heygen:
            heygen_scene(name)

    print(f"CHAIN COMPLETE: {len(names)} scene(s)"
          + ("" if heygen else " (heygen skipped)"), flush=True)

if __name__ == "__main__":
    main(sys.argv[1:])
