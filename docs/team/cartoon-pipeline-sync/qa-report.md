# QA report — dub sync gate (cartoon-pipeline)

Gate: `tools/cartoon-pipeline/5_sync_check.py` — independent measurement of the
dubbed clips (band-passed RMS envelope for timing, whisper for content).
Criteria per line: |start_off| ≤ 0.25s, |end_off| ≤ 0.35s, coverage ≥ 0.90,
tempo ∈ [0.90, 1.60], all scripted words present in order.

## Final run — ALL LINES PASS (11/11)

```
scene          ln voice         flap           st_off  end_off  cover  tempo  verdict
s1_desk        0   0.02- 3.76   0.00- 3.82   +0.02    -0.06    98%   0.94  PASS
s1_desk        1   5.02- 7.70   5.02- 7.50   +0.00    +0.20   100%   1.45  PASS
s2_whiteboard  0   0.02- 2.64   0.00- 2.64   +0.02    +0.00    99%   1.12  PASS
s2_whiteboard  1   4.60- 6.74   4.60- 6.74   +0.00    +0.00   100%   1.15  PASS
s3_shock       0   0.02- 2.92   0.00- 3.04   +0.02    -0.12    95%   1.09  PASS
s3_shock       1   3.90- 6.18   3.86- 6.04   +0.04    +0.14    98%   1.45  PASS
s4_facepalm    0   0.02- 2.68   0.00- 2.70   +0.02    -0.02    99%   1.08  PASS
s4_facepalm    1   4.40- 6.70   4.40- 6.68   +0.00    +0.02   100%   1.45  PASS
s5_shoulder    0   0.02- 2.82   0.00- 2.86   +0.02    -0.04    98%   1.15  PASS
s5_shoulder    1   3.00- 3.58   2.98- 3.60   +0.02    -0.02    94%   1.29  PASS
s5_shoulder    2   4.30- 5.92   4.30- 5.98   +0.00    -0.06    96%   1.23  PASS
```

Transcript check: every scripted word detected in order in all 5 dubbed clips
(including the tempo-1.45 takes). Deliverable recomposed: `dilbert_cartoon.mp4`
(45.1s, 1080x1920).

## Iteration history (what the gate caught)

| Run | Result | Defect found |
|-----|--------|--------------|
| v3.1 | 10 FAIL | placement used file durations — TTS breath tails over-stretched every line |
| v3.2 | 8 FAIL | tempo floor undershoots wide windows; detector threshold vs soft attacks |
| v3.3 | 3 FAIL | short lines need slower TAKES (measured pace), not clamps |
| v3.4 | 1 FAIL | clip-start lines: negative-adelay clamp played silent lead-in (energy profile: silence to 260ms) |
| v3.5 | **0 FAIL** | `atrim` lead-in in filter graph; speech lands exactly on flap start |

## Addendum — scene re-rolls (design review) + defective-take catch

After the design-critic review, s1 (engineer clone extra, missing keyboard) and
s3 (location swap) keyframes were regenerated and their Veo scenes re-rolled.
The stale-window hazard flagged by code review was real: re-rolled clips keep
the same 8.000s duration, so the windows cache now keys on clip mtime.

The gate then caught a **defective TTS take**: the s3 "measured" take had
dropped the words "it's LIVE?" (confirmed by both whisper and Gemini
transcription of the raw take), yet won selection because its duration best
fit the window. Fix: every take is transcript-verified before selection
(`valid_take` in 4_dub_voices.py); the take was re-rolled.

Final state after re-rolls: **ALL 11 lines PASS** (start offsets ≤ 0.06s,
coverage 92–100%, transcript complete). Deliverable: `dilbert_cartoon.mp4`
(= `dilbert_cartoon_v2.mp4`).

## Addendum 2 — speaker attribution (user-caught defect class)

User review found "the wrong person talking in a couple spots" — a defect class
none of the timing gates could see: timing was perfect, but the WRONG
character's mouth was moving. An 11-agent visual fan-out over per-line frame
strips attributed mouth movement and found exactly 2 mismatches:

- s3 line0: the engineer's keyframe baked-in OPEN-mouth alarm flapped through
  the boss's whole line. Fix: targeted Nano edit of the exact keyframe (close
  the engineer's mouth only), Veo re-roll with explicit mouth direction.
- s5 line2: the boss mouthed only half his punchline then closed/drifted while
  the engineer's sip animation opened. Fix: action-prompt direction ("mouth
  moves ONLY while that character speaks"; silent closed-mouth sip), re-roll.

New pipeline stage `6_speaker_check.py` automates this check (Gemini vision on
per-line frame strips). Final build passes all three gates:
timing per-scene 11/11 · timing on composed file 11/11 · speaker 11/11.
Deliverable: `dilbert_cartoon.mp4` (= `dilbert_cartoon_v3.mp4`).
