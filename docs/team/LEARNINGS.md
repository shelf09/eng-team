# LEARNINGS

Shared project memory. Written only by /eng-team:learn; other roles read.
Memory started empty on 2026-07-22.

## Patterns

## Pitfalls

- [2026-07-22] Generated END keyframes leak invented title cards unless their
  prompt explicitly forbids text — and stage 1's continuity seeding copies the
  leak into the NEXT scene's start keyframe, so one tainted end frame infects
  scenes downstream ("OPTIMIZING FOR 'HUH?'" spread across s1-s4 of
  ai_age_filter).
  Evidence: commit c66cbae (brief + prompts fixed, 6 keyframes regenerated,
  3 scenes re-rolled)  Status: active
- [2026-07-22] The pipeline gates verify audio timing and mouth attribution,
  not pixels — stray on-screen text in scene tails/opens sails through both
  gates. Scan clip openings, tails, and mid-crossfade frames for text before
  shipping (the leak above passed sync 10/10 and speaker ALL PASS).
  Evidence: commit c66cbae; boundary sweep logs in
  docs/team/clip-chain-heygen/qa-evidence/live_ai_age_filter_gates.txt
  Status: active

## Preferences
