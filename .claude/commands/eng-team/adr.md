---
description: Architecture Decision Record — captures the decision, its options, and its consequences.
argument-hint: [the decision to record — e.g. "SQLite vs Postgres for local-first sync"]
---

# Power Tool: ADR Writer

You are recording an Architecture Decision Record. An ADR exists so that in a year,
someone can find out *why* — without archaeology, without asking someone who left.
Your standard: **if the rejected options sound stupid, you wrote propaganda, not a
record.**

**Decision to record:** $ARGUMENTS

If no decision was given, mine the current diff and recent commits for an implicit
architectural decision that was just made but never recorded — a new dependency, a
changed data model, a new boundary. If several qualify, record the one most expensive
to reverse and list the rest as candidates. If none qualify, say so and stop; never
invent a decision to have something to write.

## Process

1. **Find the ADR home.** Look for an existing `docs/adr/`, `docs/decisions/`, or
   `adr/` directory and match its numbering and template exactly — the project's
   house format beats the template below. If none exists, create `docs/adr/` and
   start at `0001`.
2. **Check for conflicts.** Scan existing ADRs for one this decision reverses or
   amends. If found, this ADR supersedes it: link both ways and flip the old record's
   status to `superseded by NNNN`. Two ADRs both claiming to be current is worse
   than none.
3. **State the context as forces, not narrative** — the constraints, requirements,
   and existing realities that make this decision necessary at all. Pull real facts
   from the repo (current stack, scale hints, existing patterns), each with a
   file:line or commit sha as evidence.
4. **Give every serious option a fair hearing.** 2-4 options, each with honest pros,
   cons, and cost to reverse. Include "do nothing" when it is a real option.
5. **Record the decision and its consequences — including the negative ones.**
   Every real decision buys something and costs something; an ADR without downsides
   is missing information, not describing a perfect choice.

## Output format

Write `docs/adr/NNNN-<kebab-title>.md` (or the project's existing ADR home, in its
template), then confirm the path and show the record:

```
# NNNN. <Title — the decision stated as one line: "Use X for Y">

Date: <today>
Status: proposed | accepted | supersedes NNNN

## Context
<the forces: facts from this repo with file:line or commit evidence, not generic essays>

## Options considered
### Option A: <name>
- Pros:
- Cons:
- Cost to reverse:

### Option B: ...

## Decision
<what we are doing, in one paragraph. Then: why A beat B, specifically.>

## Consequences
- Positive: <what this buys us>
- Negative: <what it costs — every real decision has these>
- Tripwire: <the observable signal that would mean we chose wrong>
```

## Rules

- One decision per ADR. Two decisions = two files.
- Status is `proposed` unless the user says it's decided.
- The tripwire line is mandatory — it is what makes an ADR revisitable instead of dogma.
- Negative consequences are mandatory. "No downsides" means you stopped looking too soon.
- Keep it under a page. An ADR that takes ten minutes to read doesn't get read.
