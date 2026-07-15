---
description: Run the whole team — full pipeline from product review to shipped PR.
argument-hint: [the feature or change to take through the pipeline]
---

# Power Tool: Full Team Pipeline

You are the coordinator running the entire virtual engineering team on one piece
of work, end to end. Each role's instructions live in `.claude/commands/eng-team/` — when a
stage runs, follow that role's file as if it had been invoked directly, and hold
its output to that file's format. **A verdict softened in transit is a lie: every
stage's verdict reaches the user verbatim, and a gate that didn't run to its own
file's standard didn't run.**

**The work:** $ARGUMENTS

If no work is described, stop and ask — the pipeline needs a goal, not a guess.

## Process

1. **Fix the slug once.** Resolve `<feature-slug>` from $ARGUMENTS, else the
   current branch name, else the newest `docs/team/*/` directory, else slugify
   the work. Announce it and hand it to every stage, so all artifacts land in
   one `docs/team/<feature-slug>/` directory instead of drifting across several.
2. **Run the stages in order.** Each stage is a gate: collect its verdict,
   resolve blockers before moving on, and post a one-line scoreboard update
   (`[stage n/8] <role> → <verdict>`) so the user can follow along.

```
0. OFFICE HOURS (office-hours.md) → optional: run first when the idea is fuzzy;
                                    its design-doc.md feeds stage 1.
1. CEO (ceo.md)                   → worth building? BUILD proceeds. RESHAPE stops
                                    to confirm the new shape. KILL or PARK ends
                                    the run.
2. PM (pm.md)                     → prd.md: user stories + acceptance criteria —
                                    QA verifies against exactly these in stage 7.
3. EM (em.md)                     → architecture.md: locked decisions + tickets.
3.5 SPEC (spec.md)                → optional, when behavior is subtle: its
                                    Behaviors become /tdd's slices and QA's cases.
4. BUILD (tdd.md)                 → implement the tickets test-first, riskiest
                                    first, within the EM's guardrails: red before
                                    green, one vertical slice at a time; follow
                                    docs/team/<feature-slug>/plan.md if /autoplan
                                    produced one.
5. QUALITY GATES (parallel)       → three subagents on the completed diff — one
                                    message, parallel Task calls, each getting
                                    the diff scope and the slug:
                                    - code-reviewer (.claude/agents/eng-team/code-reviewer.md)
                                    - security-auditor (.claude/agents/eng-team/security-auditor.md)
                                    - design-critic (.claude/agents/eng-team/design-critic.md)
                                      [if no UI changed: record "skipped — no UI"
                                      without spawning it]
6. FIX                            → resolve every CRITICAL, HIGH, or BLOCKER
                                    finding; re-run the gate that raised it until
                                    it comes back clean or the user waives it.
7. QA (qa.md)                     → real-browser (or real-CLI) verification
                                    against stage 2's acceptance criteria. FAIL
                                    loops back to FIX. An app that won't run is
                                    FAIL with the error — never a skip.
8. RELEASE (release.md)           → gates, changelog, PR. Without gh, release
                                    pushes and hands over manual PR steps
                                    (PUSHED — NO GH); report that, don't fake a URL.
```

## Rules

- **Scope is frozen at stage 3.** If building reveals the architecture is wrong,
  return to the EM stage explicitly and rerun 3.5–4 — never quietly redesign
  mid-build.
- **Gates cannot be skipped silently.** Only the user can waive a finding; every
  waiver lands in the final report with who waived it (the user) and why.
- **Stop-and-ask points:** no work described; stage 1 verdict RESHAPE (confirm
  the new shape); a gate finding that needs a waiver; before stage 8 (confirm
  ship). Everything else runs autonomously.
- **Stages read and write `docs/team/<feature-slug>/` artifacts** (design-doc.md,
  prd.md, architecture.md, spec.md, plan.md, qa-report.md) so later stages
  inherit earlier decisions. A consumer never fails on a missing artifact — the
  role file derives or asks, and you note the gap in the scoreboard.
- **Pitfalls discovered mid-run route through /learn** — list them as ready-to-run
  commands in Follow-ups; never write docs/team/LEARNINGS.md directly.

## Output format

```
# Team Run: <work>

## Result: SHIPPED <PR URL> | PUSHED — NO GH | STOPPED AT STAGE <n> (<one-line why>)

| Stage | Verdict | Key output |
|-------|---------|------------|
| 0 Office Hours | <verdict or skipped> | design-doc.md |
| 1 CEO | BUILD/RESHAPE/KILL/PARK | <one-line rationale> |
| 2 PM | | prd.md: <n> stories |
| 3 EM | | architecture.md: <n> tickets |
| 3.5 Spec | <verdict or skipped> | spec.md: <n> behaviors |
| 4 Build | | <files changed, tests added/passing> |
| 5 Review | | <findings: fixed/waived> |
| 5 Design | <verdict or skipped — no UI> | <findings: fixed/waived> |
| 5 Security | | <findings: fixed/waived> |
| 7 QA | PASS/PASS WITH ISSUES/FAIL | <cases passed/failed>, qa-report.md |
| 8 Release | | <PR URL or branch + manual steps> |

## Waived findings
<finding — waived by the user — why. Or "none">

## Follow-ups
<deferred work as ready-to-run commands, e.g. "/tech-debt src/api",
"/learn pitfall: <what bit us>" — or "none">
```
