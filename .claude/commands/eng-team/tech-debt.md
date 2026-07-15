---
description: Tech Debt Auditor — finds, prices, and ranks the debt into a payable backlog.
argument-hint: [path to audit, or leave empty for the whole repo]
---

# Power Tool: Tech Debt Audit

You are auditing technical debt. Debt isn't "code I'd write differently" — it's code
that **taxes every future change**. Your job is to find it, price it, and rank it so
the team can pay down the expensive stuff first and consciously ignore the rest.

**Scope:** $ARGUMENTS (default: the whole repository)

## What you inventory

1. **Declared debt** — `git grep -nE "TODO|FIXME|HACK|XXX|@deprecated"`. Age the ones
   that matter — anything in a hotspot file, plus the oldest-looking — with
   `git blame -L <n>,<n> --date=short <file>`: a 2-year-old TODO is either urgent or
   deletable, never neutral. Census the rest by count.
2. **Duplication** — the same logic implemented twice-plus (similar function names,
   repeated literal blocks). Duplication is debt only when the copies must stay in
   sync — check whether they've already drifted; the drift is the evidence.
3. **Dead weight** — exports with no importers, dependencies in the manifest with no
   imports, feature-flagged code where the flag never flips, commented-out blocks.
4. **Test debt** — modules with meaningful logic and zero tests; tests that assert
   nothing; skipped tests with no ticket.
5. **Dependency debt** — run the ecosystem's outdated check (`npm outdated`,
   `pip list --outdated`, `bundle outdated`); flag majors behind, unmaintained
   packages, and anything with known advisories. No manifest, no network, or no
   tool means this category is "not checked" — with the reason.
6. **Hotspot debt** — files that are both large and frequently changed:
   `git log --since="12 months ago" --format= --name-only | grep -v '^$' | sort | uniq -c | sort -rn | head -20`,
   cross-checked against `wc -l`. Complexity in a file nobody touches is free;
   complexity in a hotspot taxes every change.

## Process

1. **Resolve scope.** If $ARGUMENTS names a path, restrict every search and the
   hotspot query (`git log ... -- <path>`) to it. Read `docs/team/LEARNINGS.md` if
   present — Pitfalls may already name known debt; Preferences may record debt the
   team consciously keeps. Cite what you used, or note it's missing and move on.
2. **Run the hotspot query first.** It prices everything else: the same flaw is a
   quick win in a dead file and the top of the backlog in a hotspot. A shallow clone
   or a young repo weakens this signal — say so and lean on file size and structure.
3. **Sweep all six categories.** Every category ends in exactly one state: findings,
   cleared, or not checked (with the reason).
4. **Price each finding:**
   - **Interest** — how often it taxes a change (hotspot rank and commit counts, not vibes).
   - **Principal** — effort to fix: S (<1h) / M (a day) / L (multi-day).
   - **Risk** — what could break during the payoff, and whether tests cover it.
5. **Rank by interest against principal.** High interest, small principal goes first.
   L items don't enter the backlog whole — cut a ≤1-day first slice, or park them on
   the ignore list with the reason.
6. **Write the ignore list.** Everything found but not ranked gets a line and why
   it's cheap to keep. Unranked debt causes guilt, not action.
7. **Force the verdict** (see Rules).

## Output format

```
# Tech Debt Audit: <scope>

## Verdict: UNDER CONTROL | PAY AS YOU GO | STOP DIGGING

## Top of the backlog (pay these)
| # | Item | Where | Interest | Principal | Risk | First step |
|---|------|-------|----------|-----------|------|------------|

## Ignore list (consciously unpaid)
| Item | Why it's cheap to keep |
|------|------------------------|

## Declared-debt census
<TODO/FIXME/HACK counts, the oldest with its age, and any that are now lies>

## Quick wins (S-sized, do today)
- <item> — <ready-to-run instruction>

## Cleared / not checked
<categories swept with no findings; checks that couldn't run here, and why>
```

## Rules

- Every item carries evidence: a path, a count, an age, or a hotspot rank. No vibes.
- The verdict is forced: high-interest debt in a top-5 hotspot means at least PAY AS
  YOU GO; when changing the hotspots means mostly paying interest, STOP DIGGING.
- The ignore list is mandatory and is half the value of the audit.
- Don't propose rewrites. The unit of payoff is a day or less per item, and fixes
  use what the project already has.
- A check that couldn't run appears under "not checked" with the reason — never
  silently dropped, never guessed at.
- Debt with a recurring cause is a Pitfall: route it through /learn — LEARNINGS.md
  is read-only here.
