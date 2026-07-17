# PRD: Per-scene clip chain — start+end keyframes, Veo, optional HeyGen

## Problem
Producing one 45-second short currently means paying for every scene's video
render up front and only discovering bad scenes after composing the whole video —
the last build re-rolled 2 of 5 scenes after full spend. Scene endings are
uncontrolled: the video model improvises from a single starting image, which is
where every scene-consistency defect in the QA record originated (location swap,
duplicate character, mouth drift). Lip-sync beyond mouth-flap timing requires a
manual upload to an external tool today.

## Sources
- `docs/team/clip-chain-heygen/design-doc.md` — CEO Verdict (BUILD; HeyGen
  optional, no new orchestration infra, sequential loop). Scope inherited.
- `docs/team/cartoon-pipeline-sync/design-doc.md` + `qa-report.md` — defect
  history grounding the problem statement.
- `tools/cartoon-pipeline/README.md` — current pipeline shape and costs.
- No `docs/team/LEARNINGS.md` exists (gap noted).

## Who it's for
Curt, a solo creator iterating on a 5-scene satirical cartoon short at
~$1.20/scene, at the moment he discovers scene 3 is broken — after paying for
scenes 4 and 5.

## v1 scope

### Story 1: End keyframe per scene
As the creator, I want each scene to get a generated end keyframe in addition to
its start keyframe, and both passed to the video model as first/last frame, so
that scene endings are constrained instead of improvised.
- Given a scene in `scenes.json` with an `end_keyframe` prompt, When the
  keyframe stage runs, Then `keyframes/<scene>_end.png` is created alongside
  `keyframes/<scene>.png`, and rerunning skips both (resumable).
- Given both keyframes exist, When the Veo stage submits that scene, Then the
  request carries the start image as first frame and the end image as last frame
  (verifiable in the logged/dry-run request body).
- Given a scene with no `end_keyframe` key, When either stage runs, Then
  behavior is identical to today (start image only) — existing scenes.json files
  keep working unmodified.

### Story 2: Sequential per-clip chain, fail-fast
As the creator, I want one command that takes each scene through
keyframes → Veo clip → (optional HeyGen) before touching the next scene, and
stops at the first failure, so that a bad scene costs one clip, not the batch.
- Given 5 scenes and an empty build dir, When the chain runs, Then scene 1's
  clip is on disk before any Veo submission exists for scene 2 (observable in
  `veo_ops.json` ordering).
- Given scene 2 fails (keyframe, Veo op, or download), When the chain reaches
  it, Then the chain exits nonzero naming the failed scene and stage, and no
  Veo operations were ever submitted for scenes 3–5.
- Given a run interrupted after scene 2, When the chain reruns, Then scenes 1–2
  are skipped via the existing exists-on-disk resume idiom and work resumes at
  scene 3.

### Story 3: Optional HeyGen lip-sync pass per clip
As the creator, I want each finished clip optionally re-animated by HeyGen
against that scene's dubbed voice track, so that phoneme-level lip shapes don't
require manual uploads.
- Given `HEYGEN_API_KEY` is set and the HeyGen stage is enabled, When a scene's
  clip completes, Then the clip and that scene's audio are submitted to HeyGen,
  and `clips/<scene>_heygen.mp4` exists before the next scene begins.
- Given the HeyGen stage is not enabled (flag absent or key missing), When the
  chain runs, Then the HeyGen step is skipped with a logged note and the chain
  completes normally (exit 0).
- Given HeyGen rejects a scene or its job fails, When the chain processes that
  scene, Then the chain exits nonzero with the scene name and HeyGen's error —
  fail-fast, same as any other stage.
- Given `clips/<scene>_heygen.mp4` exists, When the compose stage runs, Then it
  prefers `_heygen.mp4` over `_dub.mp4` over the raw clip (extending the
  existing dub-preference rule).

### Story 4: Continuity seeding between scenes
As the creator, I want scene N's end keyframe attached as a reference image when
generating scene N+1's start keyframe, so that adjacent scenes share set and
lighting by construction.
- Given scene N has an end keyframe and scene N+1's start keyframe doesn't
  exist yet, When the chain generates scene N+1's start keyframe, Then scene
  N's end keyframe is included in the reference images for that request.
- Given scene 1 (no predecessor), When its start keyframe is generated, Then
  only the standing `refs/` images are attached (unchanged behavior).

## Explicitly later (cut from v1)
- Per-clip dub + sync/speaker gates inside the loop — the dub stage is
  whole-build today; restructuring it per-scene is its own project.
- Parallel Veo submissions with per-clip checkpoints — sequential is the point
  of v1; revisit only if wall-clock cost hurts.
- Auto-retry / re-roll of a failed scene — v1 stops and lets the human decide.
- Moving cartoon-pipeline to its own repo (standing product-review verdict) —
  packaging, not this feature.

## Success metric
Veo dollars spent past the first failing scene, per short: today the batch
submits all scenes up front (~$6 exposed); success is $0 — measured directly
from `veo_ops.json` submission order versus the chain's logged stop point on
the next real production run.

## Open questions
- Which HeyGen API product does the account's plan expose for
  video-in/lip-sync-out (the manual `dilbert_cartoon_heygen.mp4` flow used the
  web app)? The EM must lock the endpoint against HeyGen's public API docs; if
  the plan turns out not to expose one, Story 3 ships behind its flag as
  submit-and-fail-cleanly.

PRD ready for `/em` to architect.
