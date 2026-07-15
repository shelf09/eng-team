---
description: Adversarial Review Panel — independent second opinion from three blind, hostile parallel reviewers.
argument-hint: [branch, PR number, or leave empty for the current diff]
---

# Power Tool: Adversarial Review Panel

One reviewer has one blind spot. You convene a panel that has never met: each
panelist reads the same diff cold and attacks it from a different angle, because
**agreement is only meaningful between reviewers who could not copy each other.**

**Target:** $ARGUMENTS

If no target was given, review `git diff` + `git diff --staged` (fall back to the
last commit if the tree is clean). If a branch was given, review
`git diff <default-branch>...<branch>`. If a PR number was given, use
`gh pr diff <n>`; when `gh` is missing or unauthenticated, say so, review the
local branch diff instead, and record the substitution in Panel notes.

## Process

1. **Capture the diff once.** Write it to a single scratchpad file. Every panelist
   reads those identical bytes — never a re-run of git, because the working tree
   may have moved. An empty diff ends the run: say so and stop.
2. **Spawn three panelists in one message** (three parallel Agent calls). Parallel
   spawning is the blinding mechanism: no panelist's output exists before another
   starts, so nothing can leak between them. Each panelist's prompt contains
   exactly three things — the diff file path, its own lens below verbatim, and the
   reporting contract (findings with file:line plus a concrete failing input, a
   cleared list, no preamble). The prompt must not mention the other panelists,
   their lenses, any prior review, or anything else from this conversation.
   - **Correctness skeptic:** "Assume this change is broken. Find how." Inputs,
     boundaries, callers, state, concurrency.
   - **Security paranoid:** "Assume this change is exploitable. Find the path."
     Untrusted input reaching dangerous sinks, authz gaps, leaked secrets. May be
     omitted ONLY when the diff touches no input handling and no trust boundary —
     record the omission and its reason in Panel notes.
   - **Devil's advocate:** "Argue this change is UNSAFE to merge." Steelman the
     opposition: contract breaks, migration risk, rollback story, blast radius.
3. **Locate the prior review, if any.** A `/reviewer` or `/preflight` report from
   earlier in this conversation, or a report the user pointed to in the target.
   If none exists, write "no prior review" in Panel notes and cross-corroborate
   the panelists against each other only.
4. **Overlap analysis.** Build one ledger of every finding from every source
   (panelists plus prior review). Two findings match when they name the same file,
   overlapping lines, and the same failure mechanism — wording differences don't
   matter; different mechanisms on the same line are different findings. Then:
   - **Two or more independent sources** → corroborated. Report as a finding at
     the highest severity any source claimed.
   - **Exactly one source** → verify it yourself before reporting: trace a
     concrete failing input through the code. Verified → finding. Not verified →
     Suspicion.
   - **Prior-review finding no panelist re-found** → re-check it against the diff
     yourself. Still real → finding marked "prior only, re-verified". Wrong or
     already fixed → Cleared, with what you checked.
5. **Verdict.** Exactly one of the three below. "It depends" is not on the list.
   - **CONCUR** — no verified findings block the merge and the panel surfaced
     nothing new.
   - **CONCUR WITH FINDINGS** — mergeable after the listed fixes.
   - **DISSENT** — must not merge as-is; every reason carries evidence.

## Output format

```
# Second Opinion: <target>

## SECOND OPINION: CONCUR | CONCUR WITH FINDINGS | DISSENT

## Cross-review table
| Finding | Sources | Verified | Severity |
|---------|---------|----------|----------|
| <one-line defect> | skeptic + prior review | yes — <traced failing input> | CRITICAL |

## Dissent reasons
<only if DISSENT: exactly why this must not merge, each reason with file:line evidence>

## Suspicions (unverified)
<single-source findings with no traced failing input — flagged, never asserted>

## Cleared
<claims you investigated and ruled out — one line each, with what you checked>

## Panel notes
<omitted panelists + reason; prior review used or "none found"; degradations (e.g. no gh)>
```

## Rules

- Panelists never see each other's output, lenses, or any earlier review before
  writing their own — independence is the whole product. If a prompt leaked any
  of it, discard that panelist's report and re-run them blind.
- A single-source finding with no traced failing input is a suspicion, never a
  finding. Label it as one.
- CONCUR means the panel ran and you verified there was nothing new — never that
  you deferred to the first review.
- Every dissent reason carries evidence: file:line plus a traced failing input or
  a measurement.
- Cap: 10 rows in the cross-review table, worst first.
