# QA Report: per-scene clip chain (start+end keyframes → Veo → optional HeyGen)

## Verdict: PASS WITH ISSUES

Every PRD criterion was executed against the real CLI to the depth this
environment allows, and all executed cases passed. The "issues" are three
live-API surfaces that cannot be executed here (no `GEMINI_API_KEY` /
`HEYGEN_API_KEY` in this session; live runs also spend real money and upload
media). They are listed under Not tested with the exact commands for a
supervised live run — ship-gating them is the user's call at the release stop.
Where the PRD itself designates a non-live verification surface ("verifiable in
the logged/dry-run request body", Story 1), that surface was executed for real.

## Environment
- macOS (Darwin 25.3.0), Python 3.14.2, Homebrew ffmpeg, zsh
- Repo at commit 1952d12 + working tree (feature files untracked)
- CLI degradation per qa.md: this project has no UI — cases are real CLI
  invocations asserting exit codes, stdout, and on-disk effects; evidence =
  captured command output in `qa-evidence/`. A browser wasn't applicable.
- No API keys in the session; external calls stubbed at documented seams only
  (`HEYGEN_LIPSYNC` override; harness scripts drive the real `submit()`/`gen()`
  and log the outgoing request bodies).
- Sandboxes: A = complete build (10 keyframes, 5 real Veo clips + 5 dubs),
  B = only scene 1 complete, C = A clone for failure injection, D = mixed
  clip tiers for compose.

## Test basis
`docs/team/clip-chain-heygen/prd.md` acceptance criteria (all 4 stories).
No `spec.md` (skipped by design), no `docs/team/LEARNINGS.md` (gap noted).

## Results
| # | Case | Expected | Actual | Status | Evidence |
|---|------|----------|--------|--------|----------|
| Q1 | Chain over complete build (resume) | exit 0, every stage skips, CHAIN COMPLETE | exit 0, 15 "exists, skipping" | ✅ | qa-evidence/q01_chain_resume.txt |
| Q2 | `0_chain.py s3_shock` re-roll | only s3 processed, exit 0 | s3-only output, exit 0 | ✅ | qa-evidence/q02_chain_one_scene.txt |
| Q3 | Unknown scene name | exit ≠0, names it | exit 1, `unknown scene(s): ['nope']` | ✅ | qa-evidence/q03_chain_unknown_scene.txt |
| Q4 | `--heygen` without key (Story 3 c2) | skip note, exit 0 | "HEYGEN_API_KEY not set — skipping", exit 0 | ✅ | qa-evidence/q04_heygen_no_key.txt |
| Q5 | `--heygen` + stub client (Story 3 c1, chain side) | wav per scene, client argv w/ --confirm-upload, `_heygen.mp4` before next scene, exit 0 | all 5 produced, argv recorded, exit 0 | ✅ | qa-evidence/q05_heygen_stub_success.txt |
| Q5b | Rerun with `_heygen.mp4` present | 5 skip lines, exit 0 | 5× "heygen exists, skipping", exit 0 | ✅ | qa-evidence/q05b_heygen_rerun_skips.txt |
| Q6 | HeyGen step fails (Story 3 c3) | exit ≠0 naming scene+stage, scene 2 untouched | `CHAIN STOPPED at s1_desk / heygen lipsync (exit 1)`, zero s2 activity | ✅ | qa-evidence/q06_heygen_failure_stops_chain.txt |
| Q7 | Real HeyGen client accepts chain argv (dry-run) | POST body: mode precision, dynamic duration off | exactly that, exit 0 | ✅ | qa-evidence/q07_heygen_client_dryrun_contract.txt |
| Q8 | Veo request body via real `submit()` (Story 1 c2/c3) | no `_end.png` ⇒ no lastFrame; with ⇒ lastFrame, bytes match | keys `['image','prompt']` vs `['image','lastFrame','prompt']`, bytes match True | ✅ | qa-evidence/q08_veo_request_body_logged.txt |
| Q9 | Compose preference (Story 3 c4) | heygen > dub > raw per scene | exactly that mapping | ✅ | qa-evidence/q09_compose_preference.txt |
| Q10 | List mode with cover.png (fix regression) | exit 0, no cover work | exit 0, 0 cover artifacts | ✅ | qa-evidence/q10_compose_list_skips_cover.txt |
| Q11 | Continuity seeding via real `gen()` (Story 4) | s1 start: refs only; s1 end: +own start; s2 start: +s1 end | exactly that | ✅ | qa-evidence/q11_nano_continuity_seeding.txt |
| Q12 | Malicious scenes.json name `../evil` (security fix) | exit ≠0 before any work | exit 1, `invalid scene name(s)` | ✅ | qa-evidence/q12_invalid_scene_name_guard.txt |
| Q13 | Fail-fast, zero spend past failure (Story 2) | s1 resumes, stop at s2/keyframes, no Veo ops | exit 1, `CHAIN STOPPED at s2_whiteboard / keyframes`, no veo_ops.json | ✅ | qa-evidence/q13_failfast_zero_spend.txt |

Supporting: full unit suite 68/68 OK (not counted as a ✅ case per qa.md).

## Bugs found
None during QA. (The list-mode ffmpeg spin on an undecodable cover was found
and fixed during the build/fix stages, regression-covered by Q10 and
tests/test_compose.py.)

## Not tested
- ⏭️ **Live keyframe/clip generation** (Story 1 c1's "created" half; Story 4
  live behavior): needs `GEMINI_API_KEY`; ~$0.05/image + ~$1.20/scene. Command:
  `python3 tools/cartoon-pipeline/0_chain.py` in a fresh `CARTOON_DIR`.
- ⏭️ **Live Veo acceptance of `lastFrame`** (architecture Risk #1 tripwire:
  HTTP 400 naming the field ⇒ wrong placement). First live chain run covers it.
- ⏭️ **Live HeyGen round-trip** incl. duration preservation (Story 3 c1's
  external half; architecture Risk #3 tripwire: `_heygen.mp4` duration drift
  >0.1s). Command: `python3 tools/cartoon-pipeline/0_chain.py --heygen`
  with `HEYGEN_API_KEY` set — uploads clip + audio to HeyGen.

These three require user-held keys and real spend/uploads; they are the
release-stop decision: run a supervised live QA pass, or waive for this ship
and rely on the architecture tripwires at first production use.
