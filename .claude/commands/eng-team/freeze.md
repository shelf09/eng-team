---
description: Edit Lock — freezes all writes to one directory for the rest of the session.
argument-hint: [directory to freeze to | off to release — empty infers the current module]
---

# Power Tool: Edit Lock

You are the write barrier on this session. Once frozen, this session **edits nothing
outside the frozen directory — no exceptions, no "just one import."** Reads stay open
everywhere; writes stop at the boundary. Pair with /careful for maximum-safety mode on
production work: nothing destructive runs unconfirmed, nothing outside the boundary
gets written.

**Boundary:** $ARGUMENTS

- A directory path: freeze to it. If the path does not exist, say so and ask —
  never freeze to a directory that isn't there.
- A file path: freeze to its containing directory and say you did.
- Empty: infer the module currently being worked on (files edited this session,
  `git status`, recent commits), state the inferred boundary out loud, freeze to it.
- `off` (or the user runs `/unfreeze`): release the lock and report it in unfreeze.md's
  release format — the boundary that dropped, exceptions used, and every deferred
  BLOCKED BY FREEZE edit — then stop. Both release paths surface the same record; a
  release that loses the deferred-work list is a silent skip.

## Process

1. Resolve the boundary per above and print the activation output below.
2. For the rest of the session, Write/Edit/NotebookEdit on paths under the frozen
   directory proceed normally.
3. Reads anywhere stay allowed — understanding the whole repo is encouraged.
4. When a needed change falls outside the boundary: do not make it. Report it as
   BLOCKED BY FREEZE (format below) with the exact path and why the edit seemed
   needed, then let the user decide — widen the freeze, grant a one-time exception,
   or skip. Never silently skip the fix; never silently make the edit.
5. This lock is conversational, not enforced by the harness: after any context
   compaction or summarization, re-state the active boundary in your next reply.
   For deterministic enforcement, use a PreToolUse hook in `.claude/settings.json`
   that pattern-matches write paths.

## Output format (on activation)

```
# Edit Lock: ON

Frozen to: <exact directory path>
<if inferred: "Boundary inferred from <evidence> — say /freeze <dir> to correct.">

Allowed: reads anywhere; Write/Edit/NotebookEdit under <dir>/
Blocked: any write outside <dir>/ — reported as BLOCKED BY FREEZE, never done silently

This lock is conversational — I re-state it after any compaction.
Release with /freeze off or /unfreeze.
```

## Blocked-edit report

```
BLOCKED BY FREEZE
- Path: <exact path outside the boundary>
- Wanted to: <one-line description of the edit>
- Because: <why it seemed needed for the current task>
- Your call: widen freeze | one-time exception | skip
```

## Rules

- The boundary is a directory, not "related files." No judgment-call exceptions — a
  path is either under the frozen directory or it is blocked.
- Every blocked-edit report names an exact path; "a config file elsewhere" is not a
  report.
- One-time exceptions come only from the user, one per edit, and are recorded in the
  response when used ("edited outside the freeze on explicit exception: <path>").
- Release is explicit only (`/freeze off` or `/unfreeze`). Never widen the boundary
  on your own judgment; never turn yourself off.
- After any compaction, re-state the frozen boundary unprompted — a lock nobody
  remembers is no lock.
