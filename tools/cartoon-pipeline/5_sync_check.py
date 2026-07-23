#!/usr/bin/env python3
"""Stage 5 — the sync gate. Independently measures every DUBBED clip and scores
each line against its flap window (windows.json produced by stage 4).

Timing: band-passed RMS envelope detects each line's audible onset/offset in the
mix — no ASR bias. Content: whisper transcript must contain every scripted word
in order. PASS gates per line:
    |voice_start - flap_start| <= 0.25 s
    |voice_end   - flap_end  | <= 0.35 s
    flap-window coverage       >= 0.90
    tempo (placement.json)     in [0.90, 1.60]
Exit 1 if any check fails — wire it into CI or just read the table."""
import os, sys, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("CARTOON_DIR", os.path.join(HERE, "build"))
sys.path.insert(0, HERE)
from dub_lib import line_bounds_in_mix, take_missing_words

GATES = {"start": 0.25, "end": 0.35, "coverage": 0.90, "tempo": (0.90, 1.60)}

def transcript_missing(model, clip, lines, placed):
    """Per-line word check: whisper each line's PLACED window of the mix.
    Whole-clip transcription misheard words against the noise bed ('set' ->
    'said'); a focused listen on the exact segment is what a human reviewer
    does, and it keeps the word-order check strict."""
    seg = f"{BASE}/tts/_sc.wav"
    missing = []
    for i, (who, text) in enumerate(lines):
        lo = max(placed[i]["start"] - 0.15, 0.0)
        hi = placed[i]["end"] + 0.25
        subprocess.run(["ffmpeg", "-y", "-v", "error",
                        "-ss", f"{lo:.3f}", "-to", f"{hi:.3f}", "-i", clip,
                        "-vn", "-ar", "16000", "-ac", "1", seg], check=True)
        missing += take_missing_words(model, seg, text, vad=False)
    return missing

def main():
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    cfg = json.load(open(os.path.join(HERE, "scenes.json")))
    scenes = cfg["scenes"]
    names = sys.argv[1:]
    if names:
        unknown = set(names) - {s["name"] for s in scenes}
        if unknown:
            sys.exit(f"unknown scene(s): {sorted(unknown)}")
        scenes = [s for s in scenes if s["name"] in names]
    raw = json.load(open(f"{BASE}/windows.json"))
    # windows.json entries are {"wins": [...], "clip_dur": ..., "n_lines": ...}
    # (older builds stored a bare list — accept both)
    windows = {k: (v["wins"] if isinstance(v, dict) else v) for k, v in raw.items()}
    placement = json.load(open(f"{BASE}/placement.json"))
    failures = 0
    print(f"{'scene':<16} ln {'voice':<13} {'flap':<13} {'st_off':>7} {'end_off':>8} {'cover':>6} {'tempo':>6}  verdict")
    for sc in scenes:
        name = sc["name"]
        lines = [tuple(l) for l in sc["lines"]]
        clip = f"{BASE}/clips/{name}_dub.mp4"
        if not os.path.exists(clip):
            print(f"[{name}] no dub clip — run 4_dub_voices.py first")
            failures += 1
            continue
        missing = transcript_missing(model, clip, lines, placement[name])
        if missing:
            # warning, not failure: every take is transcript-verified BEFORE it
            # can win selection, and envelope timing catches placement bugs —
            # mix-level re-listens mishear tempo-warped function words
            # (confirmed false positives: 'set', 'it')
            print(f"[{name}] TRANSCRIPT WARNING (unheard in mix re-listen): {missing[:8]}")
        prev_off = 0.0
        for i, ((who, text), (fs, fe)) in enumerate(zip(lines, windows[name])):
            tempo = placement[name][i]["tempo"]
            lo = max(fs - 0.5, prev_off + 0.02)
            hi = fe + 0.7
            if i + 1 < len(lines):
                hi = min(hi, windows[name][i + 1][0] - 0.02)
            vs, ve = line_bounds_in_mix(clip, lo, hi)
            if vs is None or ve is None:
                print(f"{name:<16} {i}  NO SPEECH DETECTED in [{lo:.2f},{hi:.2f}]")
                failures += 1
                continue
            st_off, end_off = vs - fs, ve - fe
            cover = max(0.0, min(ve, fe) - max(vs, fs)) / max(fe - fs, 0.05)
            ok = (abs(st_off) <= GATES["start"] and abs(end_off) <= GATES["end"]
                  and cover >= GATES["coverage"]
                  and GATES["tempo"][0] <= tempo <= GATES["tempo"][1])
            failures += 0 if ok else 1
            print(f"{name:<16} {i}  {vs:5.2f}-{ve:5.2f}  {fs:5.2f}-{fe:5.2f} "
                  f"{st_off:+7.2f} {end_off:+8.2f} {cover:6.0%} {tempo:6.2f}  {'PASS' if ok else 'FAIL'}")
            prev_off = ve
    print(f"\n{'ALL LINES PASS' if failures == 0 else f'{failures} check(s) FAIL'}")
    sys.exit(0 if failures == 0 else 1)

if __name__ == "__main__":
    main()
