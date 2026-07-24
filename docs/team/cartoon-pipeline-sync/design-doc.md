# Lip-sync alignment for the cartoon pipeline dub stage

**Problem (user report):** dubbed voices in `dilbert_cartoon.mp4` were out of
sync with the characters' mouth movement, after two earlier alignment attempts.

## Investigation (evidence, in order)

1. **Sequential placement (v1)** ignored the video entirely — lines played on a
   fixed clock. Worst case measured: s5 punchline voice 5.48-7.83s vs mouth
   flaps 3.6-5.4s — zero overlap.
2. **Gemini audio-window alignment (v2)** put lines inside Gemini-reported
   speech windows of the original clip. Measured against whisper word
   timestamps, Gemini's windows were **0.3-1.0s off and nondeterministic**
   (same clip, two runs: s5 line1 start 3.2s vs 2.7s). Root cause of the
   residual desync the user saw.
3. **Whisper word-aligned placement (v3, shipped)** — three further defects
   found only because an independent gate measured the output:
   - TTS wavs carry 0.2-0.5s breath/decay tails → tempo math on file duration
     over-stretched lines (voices ended -0.34..-0.51s early).
   - Short takes clamped at the 0.90x tempo floor undershot wide flap windows
     (coverage 78%) → need *slower takes*, not floors → take selection.
   - `max(delay, 0)` clamp on clip-start lines silently played the wav's
     silent lead-in first → speech landed ~0.25s late. Proven with a 10ms
     full-band energy profile (silence until 260ms). Fixed with `atrim` of the
     lead-in inside the filter graph.

## Decision

Ground truth = faster-whisper word timestamps on the original Veo clips
(deterministic, ~50ms). Both-end alignment: per-line take selection
(normal/fast/measured/slow) + tempo 0.90-1.45x so speech fills the flap
window. Hard acceptance gate measured on the OUTPUT, not the intent.

## Result (5_sync_check.py on the shipped build)

All 11 lines PASS: start offsets ≤ 0.04s (~1 frame @30fps), end offsets
≤ 0.20s, flap coverage 94-100%, tempos 0.94-1.45, transcripts word-perfect.

## Rejected alternatives

- HeyGen talking-photo re-animation (audio-first, phoneme-level sync): better
  lip shapes but discards Veo's full-scene motion; reserved as fallback.
- Re-rolling Veo scenes with slower dialogue: ~$1.20/scene, nondeterministic.
- Gate relaxation: rejected — every "measurement artifact" investigated turned
  out to be a real defect (see the adelay clamp).

## Known limit

Veo's flaps are cartoon mouth cycles, not phoneme shapes. This work makes
voice and mouth start/stop together (what viewers read as "in sync"); per-
syllable lip shapes would require audio-driven re-animation of the video.
