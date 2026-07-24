# Cartoon Video Pipeline (Nano Banana → Veo → ffmpeg)

Fully-animated cartoon shorts from a dialogue script. Stages:

```
0_chain.py         THE CHAIN: runs stages 1 -> 2 -> (optional HeyGen lip-sync)
                   one scene at a time, stopping at the first failure — a bad
                   scene costs one $1.20 clip, not the batch. Resumable; scene
                   names as args re-run just those scenes. Every episode gets
                   its own dated run folder next to its deliverables:
                   <repo>/videos/<episode>/build-<YYYYMMDD>/ (newest existing
                   build-* for the episode is reused so reruns resume;
                   $CARTOON_DIR overrides). 3_compose.sh resolves the same
                   folder, so render + stitch need no env setup.
1_nano_scenes.py   Nano Banana (gemini-2.5-flash-image) generates 4-5 scene
                   keyframes, seeded with reference art so the cast stays
                   consistent across scenes. Scenes with an "end_keyframe"
                   prompt also get <scene>_end.png; a start keyframe is seeded
                   with the previous scene's end frame for continuity.
2_veo_scenes.py    Veo 3.1 Fast animates each keyframe image-to-video with the
                   scene's dialogue IN THE PROMPT — Veo generates the voices
                   and lip-sync natively. When keyframes/<scene>_end.png exists
                   it is sent as the clip's LAST frame (first/last-frame
                   interpolation). Resumable (ops saved to veo_ops.json).
3_compose.sh       ffmpeg: auto-crops letterboxing per clip, scales to
                   1080x1920, concats title cover + scenes + end card.
                   Prefers clips/<scene>_heygen.mp4, then _dub.mp4, then raw.
4_dub_voices.py    OPTIONAL — consistent voices, word-aligned to the mouth
                   flaps. Fixed Gemini TTS voices per character; every line is
                   placed into the original clip's whisper-timed speech window
                   with take selection (normal/fast/measured/slow) so voice
                   and lips start AND stop together. Needs faster-whisper.
5_sync_check.py    The sync gate: independently measures every dubbed clip
                   (envelope timing + whisper transcript) and PASS/FAILs each
                   line. Exit 1 on any failure.
6_speaker_check.py The SPEAKER gate: timing can be perfect while the WRONG
                   character's mouth moves (e.g. the listener's shocked-open
                   mouth flaps through the speaker's line). Samples frames
                   across each line and asks Gemini vision whose mouth moves.
7_episode.py       EPISODE WRITER: Gemini writes a new 5-scene episode in the
                   show's genre — satire / dry humor about the corporate world
                   constantly making stupid decisions. Only the scenes are
                   generated; style, cast, and tts config are copied from the
                   current scenes.json. Saves episodes/<slug>.json and
                   activates it as scenes.json (validated: scene-name guard,
                   verbatim lines in action prompts, <=26 spoken words/scene).
                   Topic as args, or none to let it invent the stupid decision.
dub_lib.py         Shared audio/alignment utilities for stages 4-5.
```

## Requirements
- `GEMINI_API_KEY` in the environment (Nano Banana + Veo share it; Veo needs billing).
- `ffmpeg`, `python3` + Pillow.

## Usage
```bash
python3 7_episode.py [topic]      # optional: write + activate a new episode
python3 0_chain.py                # keyframes -> Veo per scene, fail-fast
                                  #   default veo-3.1-lite: ~$0.40/scene
python3 0_chain.py --hq           # veo-3.1-fast instead (2x cost) for finals
python3 0_chain.py --heygen       # ... plus HeyGen lip-sync per clip (uploads!)
bash 3_compose.sh out.mp4
```
Runs land in `<repo>/videos/<episode>/build-<YYYYMMDD>/` automatically, next
to that episode's finished mp4s (set `CARTOON_DIR` to override; standalone
stage scripts still default to `./build`, so export the printed run dir when
invoking a stage directly).
Or run stages batch-style as before (`python3 1_nano_scenes.py`, then
`python3 2_veo_scenes.py`); every stage also takes scene names to re-run just
those scenes (e.g. `python3 0_chain.py s3_shock`).

CAVEAT — HeyGen lipsync re-animates ONE face per video: in a two-character
shot it puts all the audio on whichever face it picks (wrong mouths, learned
the expensive way). Use `--heygen` only on single-character scenes; for
dialogue scenes use the dub stack (stages 4-6), which is the proven path.

The `--heygen` step needs `HEYGEN_API_KEY` and reuses the hardened client at
`.claude/skills/clone-video-creator/video-gen/scripts/heygen_lipsync.py`
(override with `$HEYGEN_LIPSYNC`). Audio comes from `clips/<scene>_dub.mp4`
when the dub stage has run, else the clip's own Veo audio. Passing the flag is
your consent to upload that clip + audio to HeyGen. Delete
`clips/<scene>_heygen.mp4` to re-roll one scene's lip-sync.

## Character sheets
`character-sheets/` holds the canonical model sheets (`boss_sheet.png`,
`engineer_sheet.png`): turnaround, expressions, poses, color palette, and model
notes per character. `character-sheets/panels/` has the raw white-background
panels — the turnarounds make the strongest Nano Banana reference images
(drop them in `refs/` to lock character consistency even harder).

## Editing the story
- Scenes live in `scenes.json`: each entry = keyframe prompt + Veo action/dialogue
  prompt. Keep each scene's dialogue ≤ ~8s spoken (Veo clip length).
- Voice consistency: describe each character's voice in EVERY Veo prompt
  (e.g. "smug booming baritone" / "flat deadpan monotone").
- Character consistency: put reference images in `refs/` — they're attached to
  every Nano Banana request.
- Keyframe hygiene: tell Nano "no text anywhere" (stray captions leak from refs),
  and give Veo a negativePrompt of "subtitles, captions, on-screen text".

## Voice consistency + lip alignment
Veo generates good performances but a slightly different voice per clip. For a
locked cast, run `4_dub_voices.py` (then `5_sync_check.py`): fixed Gemini TTS
voices (boss=Fenrir, eng=Iapetus) with per-character style directions,
word-aligned to the mouth flaps.

How the alignment works (each step exists because the simpler one failed):
1. **Flap windows = whisper word timestamps on the ORIGINAL clip.** The mouths
   flap exactly when Veo's own voices spoke. Gemini audio-timestamps were
   0.3-1.0s off and nondeterministic between runs; whisper is ~50ms and stable.
2. **Speech spans, not file durations.** TTS wavs carry 0.2-0.5s of breath/
   decay tail and sometimes a silent lead-in; tempo math must use the audible
   span (RMS-measured) and `atrim` the lead-in in the filter graph — a clamped
   negative adelay silently plays lead-in silence and shifts clip-start lines
   ~0.25s late (this was the last bug the gate caught).
3. **Take selection.** Per line, generate normal (plus fast / measured / slow
   when needed) and pick the take whose speech FILLS the flap window at a
   natural tempo (0.90-1.45x) — both ends align. Short lines in long windows
   need slower takes, not tempo floors; dense lines need rapid-fire takes.
4. **Gate it.** `5_sync_check.py` measures the dubbed mix independently
   (band-passed envelope onsets + whisper transcript) — per line:
   |start| <= 0.25s, |end| <= 0.35s, coverage >= 0.90, tempo 0.90-1.60.
   Achieved on the reference build: start offsets <= 0.04s, coverage 94-100%.

Per-scene `"delivery"` in scenes.json still prepends a style hint (see s5).
Every generated take is transcript-verified before it can be selected — Gemini
TTS occasionally drops words from a take, and a truncated take must never win
on duration (one re-roll, then the take is excluded).

TTS gotchas: output is raw PCM s16le@24k mono; loudnorm it, never blind
silence-trim, and prefer pacing prompts over aggressive atempo.

Other voice providers (e.g. HeyGen TTS — credits often already on hand) drop
in cleanly: the aligner fits ANY wav; swap the `tts()` call, keep everything
else. Phoneme-level lip shapes are beyond any dub — that requires audio-driven
re-animation (HeyGen-class talking-image), trading away Veo's scene motion.

## Lessons learned (July 2026 build)
- Veo animates cartoon stills best when told "keep the exact art style of the
  input image" + "static camera, slow push-in".
- Auto-detect letterbox bars per clip (`cropdetect`) — Veo 9:16 output ships
  with thin bars that vary per render.
- Homebrew ffmpeg lacks `drawtext`; bake titles as PNG overlays with Pillow.
- HeyGen avatars: only use square/portrait-preview avatars for 9:16 (landscape
  avatars letterbox) — not used in this pipeline, kept for reference.
