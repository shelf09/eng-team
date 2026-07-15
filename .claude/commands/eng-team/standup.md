---
description: Daily standup — what happened, what's next, what's blocked, from real repo state.
argument-hint: [optional: how far back to look, e.g. "3 days" (default: since yesterday)]
allowed-tools: Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(git show:*), Bash(git branch:*), Bash(git stash list:*), Bash(gh pr:*), Bash(gh issue:*), Bash(head:*), Read, Grep, Glob
---

# Power Tool: Standup

You are running the daily standup. Nobody wants a meeting; they want the three
answers, grounded in what the repository actually says — not what anyone
remembers. **If the repo can't show it, it doesn't go in the standup.**

**Lookback:** $ARGUMENTS (default: since yesterday)

## Repo state

- Branch: !`git branch --show-current`
- Working tree: !`git status --short`
- Stashes: !`git stash list`
- Recent commits: !`git log --oneline --since="yesterday" --all`
- Active branches: !`git branch -a --sort=-committerdate | head -10`

If $ARGUMENTS names a different window, re-run the log with it. On a Monday,
widen "yesterday" to "last friday" and say so in the report — a standup that
skips the weekend's work isn't a standup.

## Process

1. **Yesterday:** summarize the lookback commits by *outcome*, not by commit
   message — `git show` the significant ones and group related commits. A
   "refactor" that changed behavior gets called what it is.
2. **In flight:** describe the working tree and any stashes — what half-done
   work is sitting there? Judge from the diff whether it is active (relates to
   the window's commits) or abandoned (relates to nothing recent), and say which.
3. **Blockers:** evidence only — open PRs awaiting review and their CI status
   (`gh pr list`, `gh pr checks` when gh works), merge conflict markers,
   branches that stalled mid-window, dependency errors visible in the tree.
   Do not run the test suite — standup is read-only and fast; CI status is
   your test signal, and no CI means test health is unknown, not fine.
4. **Today:** infer the natural next steps from in-flight work, the blockers,
   TODO/FIXME lines added in the window (`git log -p` shows them as additions),
   and open issues assigned to the user (`gh issue list --assignee @me` when gh
   works). Propose a concrete top-3, ranked by value, each phrased as an
   instruction that can be pasted straight back to Claude.

## Output format

```
# Standup — <date> (lookback: <window>)

## Yesterday
- <outcome-level summary, grouped, with commit shas>
(or: "no commits in window — last activity <date>: <one line>")

## Today (proposed)
1. <most valuable next step, as a ready-to-run instruction>
2. ...
3. ...

## In flight
<uncommitted work and stashes, each judged active or abandoned>
(or: "clean tree, no stashes")

## Blockers
<evidence-backed blockers with sha / file:line / PR number, or "none found">
<if gh is missing or unauthenticated: "PR and CI status not checked — gh unavailable">
```

## Rules

- Keep the whole report under 30 lines. Standups that scroll get skipped.
- Every "yesterday" item traces to commits; every blocker to evidence — a sha,
  a file:line, or a gh output line.
- The "today" list must be actionable enough to paste back as instructions.
- An empty window is reported as an empty window — name the last active day,
  never widen silently. The declared Monday widening is the one exception.
- No gh, or not authenticated? One line in Blockers says so, and you continue
  from git alone — never guess PR or CI status.
- Standup is read-only: it never modifies the tree, runs the suite, or commits.
