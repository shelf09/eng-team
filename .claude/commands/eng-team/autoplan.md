---
description: Autoplan — one command in, a fully reviewed implementation plan out. Plan only, no code.
argument-hint: [feature to plan — or leave empty to use the newest upstream artifact]
---

# Power Tool: Autoplan

You are the planning pipeline compressed into one command. An idea goes in one
end; a plan that has already survived the team's reviews comes out the other.
**You edit the plan through each review — you do not collect opinions.** This is
plan-stage only: no code is written or changed.

**Input:** $ARGUMENTS

If empty, plan from the newest `docs/team/*/spec.md`, falling back to
`architecture.md`, then `prd.md`, then `design-doc.md`. If none exist, derive a
draft plan from the repo state and note that upstream artifacts are missing.

## Process

1. **Resolve the slug and sources.** `<feature-slug>` comes from $ARGUMENTS,
   else the current branch name, else the newest `docs/team/*/` directory, else
   slugify the assignment. Read the upstream artifacts in
   `docs/team/<feature-slug>/` in the fallback order above, and
   `docs/team/LEARNINGS.md` if it exists — entries that shaped the plan get
   named in Sources, and every artifact that fed the plan is listed there.
2. **Draft the plan.** Goal, approach, ordered tickets (size and done-means),
   risks. This draft is the document every review edits.
3. **Select reviews — deterministic, with evidence.** CEO (`ceo.md`) and EM
   (`em.md`) always run. Add a review only when its trigger fires, and cite the
   ticket or artifact line that fired it:
   - Designer (`designer.md`): a ticket creates or changes user-facing UI —
     components, templates, stylesheets, screens.
   - DBA (`dba.md`): a ticket touches schema, migrations, stored data shape, or
     adds a query pattern.
   - Security (`security.md`): a ticket adds an entry point (route, webhook,
     upload, CLI input), handles new untrusted input, or touches
     auth/secrets/permissions.
   No trigger, no review — record it as skipped with the trigger that didn't fire.
4. **Run each selected review in EDIT mode**, in order: CEO, EM, then the rest.
   For each, adopt the role's persona, standards, and verdict scale from its
   command file, aimed at the plan — not at a diff. Then apply instead of report:
   - Produce the role's findings and verdict against the current plan.
   - Edit the plan to resolve every finding the role's encoded principles can
     decide. Log each edit in that role's changelog as before → after, with why.
   - A finding that can't be fixed at plan level becomes a ticket prerequisite
     or a locked decision; one that can't be resolved at all keeps the failing
     verdict and marks the plan BLOCKED.
   - Record the post-edit verdict in the Reviews table. For the EM, record the
     LOCKED/BLOCKED verdict.
   - If the CEO verdict is KILL or PARK, stop the pipeline: write `plan.md`
     with Sources, the Reviews table, and the CEO reasoning — no tickets — and
     name the next step (`/office-hours`, or a human call).
5. **Surface taste decisions.** Anything the role files' encoded principles can
   decide, decide. Only genuine taste calls go to the user — maximum 3, each a
   concrete either/or. Fold the answers back into the plan.
6. **Write the plan** to `docs/team/<feature-slug>/plan.md` and show it.

## Output format

Write `docs/team/<feature-slug>/plan.md`:

```
# Plan: <name>

## Sources
<artifacts and LEARNINGS entries used; upstream gaps noted>

## Reviews
| Review | Ran? | Verdict (post-edit) | Trigger / skip reason |
|--------|------|---------------------|-----------------------|
| CEO | yes | BUILD | always runs |
| Designer | no | — | no UI tickets |

## Locked decisions
- <decision> — <which review or user answer locked it>

## Tickets (in order)
1. <ticket> — <size in hours/days> — done means: <observable result>

## Per-review changelog
### CEO pass
- <before → after, and why>
### EM pass
- ...

## Taste decisions put to user
<the ≤3 questions asked and the answers given — or "none needed">

Next step: implement the tickets, then `/qa`, then `/preflight`, then `/release`.
```

## Rules

- Reviews run in the role's own voice and verdict scale — a diluted review is a
  skipped review.
- Table verdicts are post-edit and honest: an unresolved finding keeps its
  failing verdict and the plan says BLOCKED. Never silently downgrade.
- Every skipped review is listed with the trigger that didn't fire.
- Maximum 3 questions to the user. Everything else is decided by the role files.
- The plan must be implementable without further questions: if a ticket needs a
  decision before it can start, the plan isn't done.
- New pitfalls discovered while planning are routed through `/learn` — this
  command never writes `LEARNINGS.md`.
