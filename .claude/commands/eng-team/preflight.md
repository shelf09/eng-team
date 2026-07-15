---
description: Pre-PR gate — reviewer, designer, security, and QA check the diff in parallel. One verdict.
argument-hint: [optional focus, e.g. "the auth changes" (default: the whole working diff)]
---

# Power Tool: Preflight

You are running preflight on the current diff — the last stop before a PR. Four
inspectors work in parallel; you merge their reports into one verdict. **You never
soften an inspector: every merged finding keeps its evidence (file:line or
screenshot), and the verdict is GO, GO WITH FIXES, or NO-GO — never "mostly fine."**

**Focus:** $ARGUMENTS (default: everything in `git diff` and `git diff --staged`,
plus untracked new files from `git status --porcelain`; fall back to the last
commit if the tree is clean)

## Process

1. **Capture the change set once.** Write the diff plus the contents of untracked
   new files to a temp file outside the repo, so every inspector reviews the
   identical change. If there is nothing to review, stop and say so — no verdict
   on an empty diff.
2. **Fan out the four inspector subagents in parallel** (a single message, four
   Task calls). Each maps to one agent file and receives the change-set location
   and the focus:
   - **code-reviewer** (`.claude/agents/eng-team/code-reviewer.md`) — bug hunt on the diff
   - **security-auditor** (`.claude/agents/eng-team/security-auditor.md`) — audit the
     diff's attack surface
   - **design-critic** (`.claude/agents/eng-team/design-critic.md`) — only if the diff
     touches UI code (components, templates, styles); otherwise mark it
     "skipped — no UI" without spawning it
   - **qa-tester** (`.claude/agents/eng-team/qa-tester.md`) — scoped to a quick smoke of
     the changed behavior (happy path + the nastiest edge case), not the full matrix
   Each agent already defers to its command-file methodology; do not restate it.
3. **Normalize severities.** Inspectors use different scales. Map before merging:
   CRITICAL/BLOCKER/HIGH → CRITICAL; MAJOR/MEDIUM → MAJOR; MINOR/NIT/LOW → MINOR.
4. **Merge.** Two findings are duplicates only when they share a root cause at the
   same file:line — keep one entry at the highest normalized severity and credit
   both inspectors. Two symptoms of one bug are one finding; similar bugs in
   different files stay separate. Rank the merged list worst-first.
5. **Verdict** (exactly one, by highest normalized severity present):
   - Any CRITICAL → **NO-GO**
   - Highest is MAJOR → **GO WITH FIXES** (list them as pre-merge musts)
   - MINOR only, or no findings → **GO**
   - An inspector that could not run (QA couldn't start the app, agent errored)
     is **NOT RUN**, never a silent pass: name the gap, cap the verdict at
     GO WITH FIXES, and add "verify <gap> manually" as a pre-merge must.

## Output format

```
# Preflight: <focus>

## Verdict: GO | GO WITH FIXES | NO-GO

| Inspector        | Verdict | Findings (C/M/m)          |
|------------------|---------|---------------------------|
| code-reviewer    |         |                           |
| security-auditor |         |                           |
| design-critic    |         | (or "skipped — no UI")    |
| qa-tester        |         | (or "NOT RUN — <reason>") |

## Must fix before merge
1. [<severity>] <finding> — <file:line> — found by <inspector(s)>

## Can ship, fix later
- [MINOR] <finding> — <file:line> — found by <inspector(s)>

## Cleared
- <one line per inspector: what it checked and found clean>

## Next step
<"/release <intent>" | fix the musts above, then re-run /preflight>
<for high-stakes changes: "/second-opinion" runs an independent adversarial panel before /release>
```

## Rules

- Inspectors run in parallel, never sequentially — preflight is meant to be fast.
- You merge reports; you don't re-litigate them. Only normalize, dedupe, and rank.
- A NO-GO must name the exact findings that caused it — no vibes-based blocking.
- NOT RUN and skipped inspectors appear in the table as such; absence of a report
  never counts as a pass.
