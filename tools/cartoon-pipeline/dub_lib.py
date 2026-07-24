"""Shared audio/alignment utilities for the dub stages (4_dub_voices, 5_sync_check).

Ground truth for lip alignment: word-level timestamps (faster-whisper) on the
ORIGINAL Veo clips — the moments the mouths actually flap. Deterministic, ~50ms.
"""
import os, re, json, math, wave, array, difflib, subprocess

def json_dump_atomic(obj, path):
    """Write JSON via tmp+rename so an interrupt can't truncate the file."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)

def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[:2]}... failed: {r.stderr[-400:]}")
    return r

def dur(p):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=nk=1:nw=1", p]).stdout.strip())

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]

def _digits_to_words(t):
    """0-99 as a single word token — whisper writes 'fifty' as '50', which must
    still match the scripted word. Longer numbers (years) stay digits, since
    scripts write those as digits too."""
    n = int(t)
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + ("" if n % 10 == 0 else _ONES[n % 10])

def norm(w):
    t = re.sub(r"[^a-z0-9']", "", w.lower())
    if t.isdigit() and len(t) <= 2:
        return _digits_to_words(t)
    return t

# ---------- RMS envelope measurement ----------

def _read_mono16k(path, band=False):
    tmp = path + ".m16.wav"
    af = "highpass=f=300,lowpass=f=3400" if band else "anull"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn",
                    "-af", af, "-ar", "16000", "-ac", "1", tmp], check=True)
    wf = wave.open(tmp, "rb")
    s = array.array("h"); s.frombytes(wf.readframes(wf.getnframes())); wf.close()
    return s

def _rms_frames(s, hop=320):  # 20ms @ 16k
    return [math.sqrt(sum(x * x for x in s[i:i+hop]) / hop)
            for i in range(0, max(len(s) - hop, 1), hop)]

def speech_span(wav_path, thr_rel=0.05):
    """(start_s, end_s) of audible speech inside a TTS wav (trims silent lead-in
    and breath/decay tails — TTS files carry 0.2-0.5s of low-energy tail)."""
    r = _rms_frames(_read_mono16k(wav_path))
    peak = max(r) or 1.0
    idx = [i for i, v in enumerate(r) if v > thr_rel * peak]
    if not idx:
        return 0.0, len(r) * 0.02
    return idx[0] * 0.02, (idx[-1] + 1) * 0.02

def line_bounds_in_mix(mix_path, search_start, search_end, cache={}):
    """Detected (onset, offset) of speech inside a window of the dubbed mix.
    Band-passed 20ms RMS; soft-attack onset rule; ignores the room-tone bed."""
    if mix_path not in cache:
        r = _rms_frames(_read_mono16k(mix_path, band=True))
        cache[mix_path] = (r, 0.08 * (sorted(r)[int(0.98 * len(r))] or 1.0))
    r, thr = cache[mix_path]
    i0 = max(int(search_start / 0.02), 0)
    i1 = min(int(search_end / 0.02), len(r) - 1)
    on = off = None
    for i in range(i0, i1):
        if r[i] > 0.6 * thr and r[min(i + 1, i1)] > thr:
            on = i * 0.02
            break
    for i in range(i1, i0, -1):
        if r[i] > thr and r[max(i - 1, i0)] > thr:
            off = (i + 1) * 0.02
            break
    return on, off

# ---------- word-level flap windows ----------

def clip_words(model, clip, tmpdir):
    wav = f"{tmpdir}/_ww.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-vn",
                    "-ar", "16000", "-ac", "1", wav], check=True)
    segs, _ = model.transcribe(wav, language="en", word_timestamps=True,
                               vad_filter=True, beam_size=5)
    words = []
    for seg in segs:
        for w in seg.words:
            n = norm(w.word)
            if n:
                words.append((n, w.start, w.end))
    return words

def match_line(words, pos, line_words):
    """Greedy sequential match; returns (start, end, new_pos) or (None, None, pos)."""
    hits, p = [], pos
    for lw in line_words:
        best = None
        for j in range(p, min(p + 6, len(words))):
            if words[j][0] == lw or difflib.SequenceMatcher(None, words[j][0], lw).ratio() > 0.75:
                best = j
                break
        if best is not None:
            hits.append(best)
            p = best + 1
    if not hits:
        return None, None, pos
    return words[hits[0]][1], words[hits[-1]][2], hits[-1] + 1

def take_missing_words(model, wav, text, vad=True):
    """Words of `text` NOT heard (in order) in a TTS take. TTS occasionally drops
    words from a take — such takes must never win selection on duration alone.
    vad=False for mix segments: VAD boundaries wobble against the noise bed and
    clip function words that a plain listen hears fine."""
    segs, _ = model.transcribe(wav, language="en", vad_filter=vad, beam_size=5)
    heard = [norm(w) for seg in segs for w in seg.text.split() if norm(w)]
    pos, missing = 0, []
    for lw in (norm(w) for w in text.split() if norm(w)):
        hit = None
        for j in range(pos, min(pos + 6, len(heard))):
            if heard[j] == lw or difflib.SequenceMatcher(None, heard[j], lw).ratio() > 0.7:
                hit = j
                break
        if hit is None:
            missing.append(lw)
        else:
            pos = hit + 1
    return missing

def flap_windows(model, clip, lines, tmpdir):
    """Per-line (start, end) speech windows of the ORIGINAL clip via whisper words.
    Lines whisper couldn't match are interpolated between their neighbours (with a
    warning) so a dropped/paraphrased Veo line can never poison the cache with None."""
    words = clip_words(model, clip, tmpdir)
    total = dur(clip)
    wins, pos = [], 0
    for who, text in lines:
        lw = [norm(w) for w in text.split() if norm(w)]
        s, e, pos = match_line(words, pos, lw)
        wins.append([s, e])
    for i, (s, e) in enumerate(wins):
        if s is None or e is None:
            prev_end = next((wins[j][1] for j in range(i - 1, -1, -1)
                             if wins[j][1] is not None), 0.2)
            next_start = next((wins[j][0] for j in range(i + 1, len(wins))
                               if wins[j][0] is not None), total - 0.2)
            lo = min(prev_end + 0.1, total - 0.5)
            hi = max(min(next_start - 0.1, total - 0.1), lo + 0.4)
            wins[i] = [round(lo, 3), round(hi, 3)]
            print(f"  WARNING: whisper could not locate line {i} "
                  f"({lines[i][1][:40]!r}) in {clip} — interpolated window {wins[i]}")
    return wins
