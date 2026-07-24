# Clip-chained generation: start+end keyframes → Veo → HeyGen, per scene

*Stub created by the team pipeline (CEO stage) — full design docs are /office-hours' job.*

## CEO Verdict

**BUILD** — with cuts. The per-scene chain (generate an 8s clip from a start AND
end keyframe, process it, then move to the next clip) attacks two documented,
recurring costs: scene-to-scene visual discontinuity (the s3 "location swap" and
s1 clone-extra re-rolls, `docs/team/cartoon-pipeline-sync/qa-report.md` Addendum)
and batch economics (~$1.20/scene paid five-at-a-time before any clip is
inspected, `tools/cartoon-pipeline/README.md`). Veo 3.1 first/last-frame
interpolation plus a sequential fail-fast loop is the smallest version worth
shipping.

Scope cuts:
- **HeyGen is an optional per-clip stage, not a mandatory link in the chain.**
  HeyGen re-animation was explicitly rejected last cycle because it discards
  Veo's full-scene motion (`docs/team/cartoon-pipeline-sync/design-doc.md`,
  Rejected alternatives) and the current dub stack passes all gates 11/11. It
  ships as the reserved fallback made runnable — like `4_dub_voices.py`, on by
  flag, skippable without breaking the chain.
- **No new orchestration infra.** A thin sequential loop over the existing
  numbered stages; no queues, no parallelism — sequential is the point.
- Packaging tension noted: the standing product-review verdict
  (`docs/team/product-review/design-doc.md`) says cartoon-pipeline belongs in
  its own repo. This work deepens that debt; moving it remains a follow-up, not
  a blocker.
