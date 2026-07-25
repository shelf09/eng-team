#!/usr/bin/env python3
"""Stage 4 (optional) — consistent voices, WORD-ALIGNED to the mouth flaps.

Veo picks a fresh voice timbre per clip; this stage replaces each clip's audio
with fixed Gemini TTS voices (scenes.json "tts") so the cast sounds identical in
every scene, and aligns every line to the original clip's mouth movement:

  1. Flap windows: faster-whisper word timestamps on the ORIGINAL clip (the
     mouths flap exactly when Veo's own voices spoke) — deterministic, ~50ms.
     Cached in $CARTOON_DIR/windows.json.
  2. Speech spans: each TTS wav's silent lead-in and breath tail are measured
     (RMS) and trimmed in the filter graph, so placement is exact.
  3. Take selection: per line, choose among normal / fast / measured / slow
     takes the one whose speech best FILLS the flap window at a natural tempo
     (0.90-1.45x). Both ends align: voice starts and stops with the mouth.
  4. Placement log written to $CARTOON_DIR/placement.json for 5_sync_check.py.

Requires: pip install faster-whisper (plus ffmpeg). Run between stages 2 and 3.
Output: $CARTOON_DIR/clips/<scene>_dub.mp4 (3_compose.sh prefers these).
TTS takes cache in $CARTOON_DIR/tts/ — delete a wav to re-roll that take."""
import os, json, base64, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("CARTOON_DIR", os.path.join(HERE, "build"))
KEY = os.environ["GEMINI_API_KEY"]

import sys
sys.path.insert(0, HERE)
from dub_lib import (sh, dur, speech_span, flap_windows, json_dump_atomic,
                     take_missing_words)

cfg = json.load(open(os.path.join(HERE, "scenes.json")))
TTS = cfg["tts"]
TTS_DIR = os.path.join(BASE, "tts")
CLIPS = os.path.join(BASE, "clips")
os.makedirs(TTS_DIR, exist_ok=True)

CAP_HI, CAP_LO = 1.45, 0.90
PACE_PREFIX = {
    "fast": "Say this EXTREMELY fast, rapid-fire, compressed, no pauses at all. ",
    "slow": "Say this slowly and deliberately, stretching every word out. ",
    "measured": "Say this at an unhurried, even pace, taking your time with each word. ",
}

def tts(line_id, who, text, delivery="", pace=""):
    wav = f"{TTS_DIR}/{line_id}{('_' + pace) if pace else ''}.wav"
    if os.path.exists(wav):
        return wav
    prefix = PACE_PREFIX.get(pace, delivery)
    body = {"contents": [{"parts": [{"text": prefix + TTS["styles"][who] + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig":
                    {"voiceName": TTS["voices"][who]}}}}}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{TTS['model']}:generateContent?key={KEY}")
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            wait = 30 * (attempt + 1)
            print(f"  tts rate-limited (429) — waiting {wait}s", flush=True)
            time.sleep(wait)
    pcm = None
    for part in resp.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "inlineData" in part:
            pcm = base64.b64decode(part["inlineData"]["data"])
            break
    if pcm is None:
        # stacked pace+style prompts sometimes make TTS return no audio
        # (finishReason OTHER) — treat the take as unavailable, don't crash
        print(f"  tts {line_id}{('_' + pace) if pace else ''} [{who}] NO AUDIO "
              f"({resp.get('candidates', [{}])[0].get('finishReason')}) — take unavailable",
              flush=True)
        return None
    raw = wav + ".pcm"
    open(raw, "wb").write(pcm)
    tmp = wav + ".tmp.wav"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", "24000", "-ac", "1",
        "-i", raw, "-af", "loudnorm=I=-17:TP=-1.5", "-ar", "44100", tmp])
    os.replace(tmp, wav)          # cache never sees a partial wav
    os.remove(raw)
    print(f"  tts {line_id}{'_' + pace if pace else ''} [{who}] {dur(wav):.2f}s", flush=True)
    return wav

def get_windows(model_holder, scene_cfg):
    """Load or build the whisper flap windows for one scene.
    Cache entries carry the clip duration + line count and are invalidated when
    either changes — re-rolling a Veo clip or editing lines forces re-measurement
    (otherwise the dub AND the gate would both silently use stale timings)."""
    path = f"{BASE}/windows.json"
    cache = json.load(open(path)) if os.path.exists(path) else {}
    name = scene_cfg["name"]
    lines = [tuple(l) for l in scene_cfg["lines"]]
    clip = f"{CLIPS}/{name}.mp4"
    clip_dur = dur(clip)
    clip_mtime = int(os.path.getmtime(clip))
    ent = cache.get(name)
    stale = (not isinstance(ent, dict)                      # old list format
             or ent.get("clip_mtime") != clip_mtime         # re-rolled clips keep the
             or abs(ent.get("clip_dur", -1) - clip_dur) > 0.05  # same 8s duration!
             or ent.get("n_lines") != len(lines)
             or any(w[0] is None for w in ent.get("wins", [[None]])))
    if stale:
        if model_holder[0] is None:
            from faster_whisper import WhisperModel
            model_holder[0] = WhisperModel("base", device="cpu", compute_type="int8")
        cache[name] = {"wins": flap_windows(model_holder[0], clip, lines, TTS_DIR),
                       "clip_dur": round(clip_dur, 3), "clip_mtime": clip_mtime,
                       "n_lines": len(lines)}
        json_dump_atomic(cache, path)
        print(f"[{name}] flap windows: "
              f"{[[round(a,2), round(b,2)] for a, b in cache[name]['wins']]}", flush=True)
    return cache[name]["wins"]

def evaluate(d, window):
    """(tempo, score): 0 = fills the window at natural tempo; else seconds of miss."""
    tf = d / window
    if CAP_LO <= tf <= CAP_HI:
        return tf, 0.0
    if tf > CAP_HI:
        return CAP_HI, d / CAP_HI - window
    return CAP_LO, window - d / CAP_LO

def valid_take(model_holder, line_id, who, text, delivery, pace):
    """Generate a take and transcript-verify it: TTS occasionally drops words, and a
    truncated take must never win selection on duration. One retry, then excluded."""
    for attempt in range(2):
        wav = tts(line_id, who, text, delivery, pace)
        if wav is None:
            continue  # no audio returned; second loop pass is the retry
        if model_holder[0] is None:
            from faster_whisper import WhisperModel
            model_holder[0] = WhisperModel("base", device="cpu", compute_type="int8")
        missing = take_missing_words(model_holder[0], wav, text)
        if not missing:
            return wav
        print(f"    {line_id}{('_' + pace) if pace else ''}: take is missing "
              f"{missing} — {'re-rolling' if attempt == 0 else 'EXCLUDED'}", flush=True)
        os.remove(wav)
    return None

def dub_scene(scene_cfg, model_holder):
    name, lines = scene_cfg["name"], [tuple(l) for l in scene_cfg["lines"]]
    delivery = scene_cfg.get("delivery", "")
    wins = get_windows(model_holder, scene_cfg)
    clip = f"{CLIPS}/{name}.mp4"
    total = dur(clip)
    inputs, filters, mixes, placements = ["-i", clip], [], [], []
    prev_end = -1.0
    for i, ((who, text), (ws, we)) in enumerate(zip(lines, wins)):
        start = max(ws, prev_end + 0.08)
        window = max(we - start, 0.3)
        cands = {}
        wav = valid_take(model_holder, f"{name}_{i}", who, text, delivery, "")
        if wav:
            cands[""] = (wav, speech_span(wav))
        tf = ((cands[""][1][1] - cands[""][1][0]) / window) if cands else 99.0
        if tf > CAP_HI:
            fw = valid_take(model_holder, f"{name}_{i}", who, text, delivery, "fast")
            if fw:
                cands["fast"] = (fw, speech_span(fw))
        elif tf < CAP_LO:
            for pace in ("measured", "slow"):
                pw = valid_take(model_holder, f"{name}_{i}", who, text, delivery, pace)
                if pw:
                    cands[pace] = (pw, speech_span(pw))
        if not cands:
            raise RuntimeError(f"{name} line {i}: every TTS take dropped words — "
                               f"try rewording the line or re-running")
        pick, (wav, (sp_s, sp_e)) = min(
            cands.items(), key=lambda kv: evaluate(kv[1][1][1] - kv[1][1][0], window)[1])
        d = sp_e - sp_s
        tempo, score = evaluate(d, window)
        limit = (wins[i+1][0] - 0.06) if i + 1 < len(wins) else (total - 0.08)
        if start + d / tempo > limit:
            tempo = min(max(tempo, d / max(limit - start, 0.3)), 1.6)
        end = start + d / tempo
        delay = int(start * 1000)
        inputs += ["-i", wav]
        # trim silent lead-in / keep 150ms decay; adelay lands SPEECH exactly at start
        filters.append(f"[{i+1}:a]atrim={sp_s:.3f}:{sp_e + 0.15:.3f},asetpts=PTS-STARTPTS,"
                       f"atempo={tempo:.3f},adelay={delay}|{delay}[l{i}]")
        mixes.append(f"[l{i}]")
        placements.append({"i": i, "who": who, "take": pick or "normal",
                           "start": round(start, 3), "end": round(end, 3),
                           "flap": [round(ws, 3), round(we, 3)], "tempo": round(tempo, 3)})
        print(f"    line{i} [{who:4}]{(' ' + pick) if pick else ''} speech {start:5.2f}-{end:5.2f} "
              f"(flap {ws:.2f}-{we:.2f}, tempo {tempo:.2f})", flush=True)
        prev_end = end
    plc = json.load(open(f"{BASE}/placement.json")) if os.path.exists(f"{BASE}/placement.json") else {}
    plc[name] = placements
    json_dump_atomic(plc, f"{BASE}/placement.json")
    filters.append(f"anoisesrc=color=brown:amplitude=0.012:d={total:.2f},lowpass=f=400[bed]")
    fc = ";".join(filters) + f";[bed]{''.join(mixes)}amix=inputs={len(mixes)+1}:normalize=0[a]"
    out = f"{CLIPS}/{name}_dub.mp4"
    sh(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc,
        "-map", "0:v", "-map", "[a]", "-c:v", "copy",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-t", f"{total:.3f}", out])
    print(f"[{name}] -> {out}", flush=True)

if __name__ == "__main__":
    names = sys.argv[1:] or [s["name"] for s in cfg["scenes"]]
    by_name = {s["name"]: s for s in cfg["scenes"]}
    model_holder = [None]  # lazy-loaded whisper model
    for n in names:
        dub_scene(by_name[n], model_holder)
    print("done — now run 5_sync_check.py")
