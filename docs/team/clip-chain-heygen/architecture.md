# Architecture: Per-scene clip chain — start+end keyframes, Veo, optional HeyGen

## Verdict: LOCKED

## Sources
- `docs/team/clip-chain-heygen/prd.md` (4 stories) and `design-doc.md` CEO
  Verdict (BUILD; HeyGen optional, sequential loop, no new orchestration infra).
- `docs/team/cartoon-pipeline-sync/design-doc.md` + `qa-report.md` — defect
  history; the dub/gate stack is proven and must not be disturbed.
- External contracts verified 2026-07-17 against ai.google.dev/gemini-api/docs/veo
  and developers.heygen.com (lipsync-speed): Veo 3.1 `lastFrame` lives in
  `instances[0]` beside `image`, is supported by `veo-3.1-fast-generate-preview`,
  and requires 8s duration (the pipeline's default). HeyGen: `POST /v3/assets`
  (multipart), `POST /v3/lipsyncs`, `GET /v3/lipsyncs/{id}`, `x-api-key` header.
- No `docs/team/LEARNINGS.md` exists (gap noted).

## Locked decisions
| # | Decision | Choice | Why | Reversal cost |
|---|----------|--------|-----|---------------|
| 1 | scenes.json schema | Additive optional per-scene `end_keyframe` (prompt string). Absent key ⇒ today's behavior, byte-for-byte. | Backward compatible; no migration. | Low — delete the key. |
| 2 | End-keyframe file | `keyframes/<scene>_end.png`, exists-on-disk resume (idiom: `1_nano_scenes.py:49-50`). | Matches the resume idiom every stage uses. | Low — rename. |
| 3 | Veo request shape | `instances[0].lastFrame = {"bytesBase64Encoded", "mimeType"}` beside the existing `image` (`2_veo_scenes.py:29-31`), attached only when `<scene>_end.png` exists. Model and duration untouched. | Same field shape as the proven `image` field; fast model supports it; 8s default satisfies the interpolation constraint. | Low — drop the field. External-contract risk tracked in Risks #1. |
| 4 | Per-scene invocation | Stages 1 and 2 accept scene names as argv (idiom precedent: `4_dub_voices.py:193`); no-arg behavior unchanged. | The chain needs per-scene granularity; this is the established way. | Low. |
| 5 | Orchestrator | New `tools/cartoon-pipeline/0_chain.py`: for each scene, subprocess stage 1 → stage 2 → optional HeyGen; first nonzero exit stops the chain naming scene+stage. Accepts scene-name argv and `--heygen`. | Thin, boring, sequential — the CEO cut forbids new infra; subprocess keeps stages standalone. | Low — delete the file. |
| 6 | HeyGen client | Reuse `.claude/skills/clone-video-creator/video-gen/scripts/heygen_lipsync.py` via subprocess (`--video clips/<scene>.mp4 --audio <wav> --out clips/<scene>_heygen.mp4 --confirm-upload`); never reimplement its HTTP. Path resolved from repo root, overridable via `HEYGEN_LIPSYNC` env. | It's tested (`tests/test_cartoon_voiceover.py`), hardened (SSRF guards, atomic download, 32MB cap), and already the proven contract. | Medium — if the skill moves repos, the env override is the escape hatch. |
| 7 | HeyGen audio source | ffmpeg-extract WAV from `clips/<scene>_dub.mp4` when present, else from `clips/<scene>.mp4`, into `$CARTOON_DIR/heygen/<scene>.wav`. | Dub-in-loop is cut from v1 (PRD); this lets a later dub run + `_heygen` re-roll upgrade lips without chain changes. | Low. |
| 8 | HeyGen timing | Script defaults: `--mode precision`, dynamic duration OFF — output keeps the 8s timing. | Compose and both sync gates assume clip duration is preserved. | Low — flag flip, but see Risks #3. |
| 9 | HeyGen enablement | `--heygen` flag AND `HEYGEN_API_KEY` set ⇒ run, fail-fast on error. Flag absent or key missing ⇒ log a skip note, exit 0 (PRD Story 3). `--confirm-upload` is passed by the chain because `--heygen` is the user's explicit upload consent. | Optional-stage semantics locked by the CEO verdict. | Low. |
| 10 | Compose preference | `_heygen.mp4` > `_dub.mp4` > raw, extending `3_compose.sh:32`. | One-line extension of the existing rule. | Trivial. |
| 11 | Continuity seeding | In stage 1: when generating scene N's start keyframe, if scene N−1's `_end.png` exists on disk, append it to the reference images after the standing `refs/`. | By-construction set/lighting continuity (PRD Story 4) with zero new state. | Low — one line; see Risks #4. |

## Rejected alternatives
- New standalone `7_heygen_lipsync.py` HTTP client in cartoon-pipeline: 300
  duplicated lines of already-hardened code, two copies to patch.
- importlib-refactor of stages into shared functions: bigger diff, breaks the
  "each numbered script is standalone" property for no capability gain.
- Chaining scene N's end frame as scene N+1's literal start frame: scenes are
  deliberate cuts (desk → whiteboard), not continuous shots; reference-seeding
  gives continuity without welding shots together.
- Batch submit with per-clip checkpoints: sequential fail-fast is the point
  (PRD Story 2); parallelism is "Explicitly later."

## Implementer's choice
- `0_chain.py` argument parsing style, log wording, and summary format.
- WAV extraction codec/rate (suggest `pcm_s16le` 44.1k — matches dub stage).
- The five `end_keyframe` prompt texts for the demo scenes.
- Test file layout under `tests/` (mirror `test_cartoon_voiceover.py` idioms:
  importlib loading, mocked `urllib`/`subprocess`).

## Tickets
### T1: Veo last-frame + per-scene argv in `2_veo_scenes.py`
- **Goal:** riskiest assumption first — the request body carries `lastFrame`
  correctly and only when the end keyframe exists.
- **Files:** `tools/cartoon-pipeline/2_veo_scenes.py`, `tests/test_veo_scenes.py` (new).
- **Acceptance criteria:**
  - With `keyframes/s.png` + `keyframes/s_end.png` present, the submitted body
    (captured via mocked urlopen) has `instances[0].lastFrame.bytesBase64Encoded`
    == the end image bytes, b64.
  - Without `s_end.png`, the body has no `lastFrame` key.
  - `python3 2_veo_scenes.py s1_desk` submits/polls only `s1_desk`; no-arg run
    still processes every scene.
- **Out of scope:** chain, HeyGen, keyframe generation.

### T2: End keyframes + continuity seeding + per-scene argv in `1_nano_scenes.py`
- **Goal:** each scene with an `end_keyframe` prompt gets `<scene>_end.png`;
  scene N's start request carries N−1's end keyframe as an extra ref.
- **Files:** `tools/cartoon-pipeline/1_nano_scenes.py`, `tests/test_nano_scenes.py` (new).
- **Acceptance criteria:**
  - Scene with `end_keyframe` ⇒ two files generated, both skipped on rerun.
  - End-keyframe prompt = `style_image + " " + end_keyframe`.
  - Scene N start request's parts include N−1's `_end.png` bytes when that file
    exists; scene 1's request carries only standing refs.
  - Argv filtering as in T1; scenes without `end_keyframe` unchanged.
- **Out of scope:** Veo, chain.

### T3: `0_chain.py` — sequential fail-fast orchestrator with optional HeyGen
- **Goal:** one command: per scene, stage 1 → stage 2 → optional HeyGen, stop on
  first failure, resumable.
- **Files:** `tools/cartoon-pipeline/0_chain.py` (new), `tests/test_chain.py` (new).
- **Acceptance criteria:**
  - Mocked-subprocess test proves ordering: scene 2's stage 1 never starts
    before scene 1's last enabled step succeeded.
  - Injected failure at scene 2 stage 2 ⇒ exit ≠ 0, stderr names `s2_*` and the
    stage, zero calls for scenes 3–5.
  - `--heygen` + key set ⇒ per scene: WAV extracted (dub preferred), reuse
    script invoked with `--confirm-upload`, `clips/<scene>_heygen.mp4` required
    before next scene; existing `_heygen.mp4` skips the step.
  - No `--heygen`, or `HEYGEN_API_KEY` unset ⇒ skip note logged, exit 0.
- **Out of scope:** dub/gates in-loop, retries, parallelism.

### T4: Compose preference, demo `end_keyframe` content, README
- **Goal:** `_heygen` clips win composition; the demo scenes exercise Story 1;
  docs match reality.
- **Files:** `tools/cartoon-pipeline/3_compose.sh`, `scenes.json`,
  `tools/cartoon-pipeline/README.md`.
- **Acceptance criteria:**
  - With `clips/s_heygen.mp4` + `clips/s_dub.mp4` + `clips/s.mp4` present,
    concat list references `_heygen`; with dub+raw, `_dub`; raw-only, raw.
  - All 5 demo scenes gain an `end_keyframe` prompt; no existing key modified.
  - README documents the chain flow, flags, and HeyGen env requirements.
- **Out of scope:** regenerating any build artifacts.

## Guardrails
- Python stdlib only (`urllib`, `json`, `base64`, `subprocess`) — no new
  dependencies; `faster-whisper` stays confined to stages 4–5.
- Do NOT modify `4_dub_voices.py`, `5_sync_check.py`, `6_speaker_check.py`,
  `dub_lib.py` — the gate stack is proven (11/11) and out of scope.
- Do NOT reimplement HeyGen HTTP anywhere in `tools/cartoon-pipeline/`.
- Preserve idioms: exists-on-disk resume, `.part` + `os.replace` atomic writes,
  `CARTOON_DIR` env, flush-printed progress.
- No Veo model change, no `durationSeconds`, no aspect-ratio change.
- `scenes.json` edits are additive only.

## Risks
1. **`lastFrame` rejected live** (docs say supported for the fast model; casing
   verified against Vertex/Gemini docs, but this env has no `GEMINI_API_KEY` to
   prove it). Tripwire: first live run returns HTTP 400 naming
   `lastFrame`/unknown field — we chose the wrong field location; check
   `parameters` placement before anything else.
2. **HeyGen 32MB simple-upload cap** — 8s Veo clips run 2–8MB today, fine.
   Tripwire: the reuse script's size error appears — switch to HeyGen's
   multipart/resumable upload, a new ticket.
3. **HeyGen alters clip duration** despite dynamic duration OFF. Tripwire:
   `_heygen.mp4` duration differs >0.1s from source — stop preferring it in
   compose until resolved; sync gates would also catch this.
4. **Continuity ref bleeds pose/layout** into scene N+1's start keyframe (a new
   character-consistency defect class). Tripwire: a start keyframe showing the
   previous scene's pose or a duplicated character — drop decision #11 (one
   line) and re-roll that keyframe.

Next step: `/tdd` against the tickets above (spec stage not needed — behavior is
mechanical; the subtle behavior is already pinned by acceptance criteria).
