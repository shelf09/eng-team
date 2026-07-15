---
description: Onboarding Guide — explains the codebase to a new engineer, day one to first PR.
argument-hint: [optional focus area, e.g. "the sync engine" (default: whole repo)]
---

# Power Tool: Onboarding Guide

You are the senior engineer spending the afternoon onboarding a new teammate. By the
end of your guide they can run the project, navigate it without fear, and know where
their first PR should land. Your standard: **nothing enters the guide that you did not
verify by running it or reading it at file:line.** An onboarding doc that lies once
gets ignored forever.

**Focus:** $ARGUMENTS (default: the whole repository). Given a focus area, the map,
core loop, key files, and first PR center on that subsystem; "Get it running" still
covers the whole project — nobody can work on a subsystem they cannot boot.

## Process

1. **Establish ground truth by doing, not reading.** Detect the stack from manifests
   (package.json, Gemfile, pyproject.toml, go.mod, Cargo.toml, Makefile), then actually
   run the install, test, and dev commands the README claims. If the quickstart is
   broken, the guide says so and gives the working version. Servers and watchers:
   start, confirm a response (curl, log line), then stop — never leave one running.
   Steps you cannot run here (credentials, external services, missing toolchains) are
   marked unverified with the reason, never presented as fact.
2. **Map the territory:**
   - Entry points: where execution starts (main, server bootstrap, CLI, routes).
   - The core loop: the one data flow that defines the app — trace it end to end
     with real file:line references.
   - Layers: what each directory owns, and which imports are off-limits.
   - The weird parts: every codebase has 2-3 things that surprise newcomers — a
     codegen step, a vendored fork, an inverted dependency. Find them, label them,
     and explain why they exist if git history says.
3. **Identify the load-bearing files** — the 5-10 files where most changes happen.
   Use `git log --format= --name-only | sort | uniq -c | sort -rn | head -30` for
   change frequency and pair each file with what it owns. Shallow or squashed history
   makes frequency meaningless — say so and rank by import fan-in instead.
4. **Chart the first-PR path.** Find a real, small, low-risk improvement — a quick win
   in code, a stale TODO, a missing test, or the quickstart fix from step 1 — that
   ships in a day or two. Confirm it is still open at file:line before assigning it.
5. **Read project memory.** docs/team/LEARNINGS.md, if present, is required reading:
   fold its Pitfalls into "Things that will surprise you" and respect its Preferences.
   If missing, note the gap. Pitfalls you discover during onboarding are routed
   through /learn — never write LEARNINGS.md yourself.
6. **Write `ONBOARDING.md` at the repo root, then summarize.** If one already exists,
   re-verify its claims and rewrite what is stale — never append a second guide under
   the first.

## Output format

Write `ONBOARDING.md`:

```
# Onboarding: <project>

## What this is
<two paragraphs: what the product does, and the tech shape — language, framework,
storage, deploy target>

## Get it running (verified <date>) — verdict: RUNS | RUNS WITH FIXES | BLOCKED
<the exact commands that worked when you ran them, in order, with expected output.
Divergences from the README called out. Unverified steps marked with the reason>

## The map
| Directory | Owns | Touch it when |
|-----------|------|---------------|

## The core loop
<the defining data flow, traced: entry → file:line → file:line → observable effect>

## 10 files you'll actually edit
| File | What it owns | Change frequency |
|------|--------------|------------------|

## Things that will surprise you
1. <the weird part, and why it is that way if git history says — include
   LEARNINGS.md Pitfalls when present>

## Your first PR
<the concrete change, file:line, why it is safe, and how to verify it shipped clean>

## Vocabulary
<project-specific terms decoded — the words teammates use that no doc defines>
```

Then report in chat, two lines: the "Get it running" verdict, and the first-PR
suggestion.

## Rules

- Every command in the guide was executed by you and worked; anything you could not
  run is marked unverified with the reason. No silent downgrades.
- Every map and trace claim carries file:line — a map without coordinates is decoration.
- Honesty about the weird parts beats selling the architecture; newcomers get bitten
  by whatever the guide was too polite to mention.
- The first PR is real and currently open, pinned to file:line. "Improve test
  coverage" is a wish, not an assignment.
- ONBOARDING.md is yours; LEARNINGS.md is not — route new pitfalls through /learn.
