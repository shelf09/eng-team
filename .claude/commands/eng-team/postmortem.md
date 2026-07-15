---
description: Blameless postmortem — reconstructs an incident from repo evidence and writes the doc.
argument-hint: [what broke — e.g. "login was down after Tuesday's deploy"]
---

# Power Tool: Postmortem

You are writing a blameless postmortem. **The goal is never who — it's what made the
mistake easy, and what change makes it hard to repeat.** An action item nobody can
start on Monday is a wish wearing a table row.

**Incident:** $ARGUMENTS

If no incident was described, mine recent history for the most incident-shaped event —
a revert, a hotfix, a fix landed at an odd hour — propose it, and confirm before
writing. If nothing qualifies, ask for one sentence about what broke and when; the
rest you reconstruct yourself. Consult docs/team/LEARNINGS.md (Pitfalls) if present —
a repeat of a recorded pitfall is itself a finding; if it's missing, note the gap.

## Process

1. **Reconstruct the timeline from evidence.** Use `git log`, `git blame`, and diffs
   around the incident window to bound five moments: last good state, breaking change
   landed, detected, mitigated (the revert or hotfix sha), resolved. Timestamps from
   commits, not guesses — the gap between break and mitigation is the minimum outage
   window the repo can prove. If `gh` is available, pull the PR thread, linked issues,
   and CI runs around the window for detection and discussion timestamps; without it,
   work from git alone and say so in the timeline.
2. **Find the trigger and the root cause — they differ.** The trigger is the commit
   or event that lit the fuse. The root cause is why the fuse existed: the missing
   test, the ambiguous API, the manual step, the config that two systems interpret
   differently.
3. **Ask "why" until you hit process, not people.** "Dev pushed a bad change" always
   has a next why: why did nothing catch it? If the evidence runs out before the
   chain completes, stop there — record "not established" and the leading hypothesis,
   clearly labeled. Never dress a hypothesis as a conclusion.
4. **Assess the blast radius honestly** — what was affected, for how long, and what
   *nearly* happened that didn't.
5. **Check for recurrence.** Search prior postmortems and LEARNINGS.md Pitfalls for
   this failure mode. A repeat incident raises the severity of the process failure
   and means the last round of action items didn't hold — say which one failed.
6. **Write action items that are real:** each one is a code/process change with a
   concrete first step — not "be more careful," not "add more testing" without
   saying which test of what.
7. **Write the doc.** Use the project's existing postmortem home if one exists
   (`docs/postmortems/`, `postmortems/`, `docs/incidents/`) and match its naming and
   template; otherwise create `docs/postmortems/YYYY-MM-DD-<incident-slug>.md`. Then
   route the root cause to project memory via /learn as a Pitfall.

## Output format

Write the file from step 7, confirm the path, then show the doc:

```
# Postmortem: <one-line incident title>

**Status:** draft — needs human review of impact numbers
**Severity:** SEV1-4 (justify; note if this is a recurrence)

## Summary
<3 sentences: what broke, impact, root cause>

## Timeline (from repo evidence)
| When | What | Evidence |
|------|------|----------|
| | last good / broke / detected / mitigated / resolved | <commit sha / PR / CI run> |
<gh unavailable? say "reconstructed from git alone" here>

## Impact
<what was affected, minimum outage window from commit evidence, near-misses —
inference marked as inference>

## Root cause
Trigger: <the commit or event that lit the fuse — sha>
<the 5-whys chain, then the actual root — or "not established from repo evidence;
leading hypothesis: ...">

## What went well / what got lucky
<detection, mitigation — and what would have made this worse>

## Action items
| # | Action | Type (prevent/detect/mitigate) | First step |
|---|--------|-------------------------------|------------|

## Open questions for humans
<production data, user impact, monitoring history — what the repo can't tell you>
```

## Rules

- Blameless is structural: no action item may target a person's behavior.
- Every timeline entry cites repo evidence; mark inference as inference.
- At least one action item must be a *detection* improvement — incidents recur,
  the question is whether you notice in seconds or hours.
- Action items use what the project already has: no metrics stack means better logs
  and a regression test, not "adopt an observability platform."
- If the evidence can't establish the root cause, the doc says so and stays draft —
  a labeled hypothesis beats a confident story.
- The root cause is a Pitfall: route it through /learn — never write
  docs/team/LEARNINGS.md directly.
