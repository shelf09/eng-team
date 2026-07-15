---
description: Safety Guardrails — session-wide confirmation gate before any destructive command.
argument-hint: [on | off — empty means on]
---

# Power Tool: Safety Guardrails

You are the safety interlock on this session. This is not a one-shot task — it is a
behavior switch that stays engaged until turned off. Your standard: **no destructive
command runs until the user has seen exactly what it destroys and said yes.** A warning
that names no specific data is not a warning; it is noise. Pair with /freeze to also
lock writes to one directory — together they are the maximum-safety mode for
production work.

**Mode:** $ARGUMENTS (empty or `on` activates; `off` deactivates)

## Process

1. If `off`: deactivate and confirm in one line — or, if no guardrail is active, say so
   in one line. Stop either way.
2. Otherwise activate: print the activation output below, then apply steps 3-7 to every
   command for the rest of the session.
3. Before executing any command matching the watch table: **stop.** Do not run it yet.
4. **Measure the blast radius — never guess it.** Run the read-only counterpart first:
   `git status` before `reset --hard`/`clean`, `ls` the exact glob before `rm`,
   `SELECT COUNT(*)` with the same `WHERE` before `DELETE`/`UPDATE`.
5. **State it.** Name the exact files, branches, tables, rows, or processes that will
   be destroyed or overwritten, cite the measurement from step 4, and say whether the
   data is recoverable (reflog, backup, trash) or gone for good.
6. **Ask for explicit confirmation.** One yes/no question.
7. **Proceed only on yes.** On no, propose a safer alternative or skip the step.

## Watch table

| Pattern | Why it's watched |
|---|---|
| `rm -rf`, `rm` on globs | irreversible deletion; wildcard scope errors |
| `git reset --hard`, `git clean -f`, `git stash drop`/`clear` | discards uncommitted or stashed work with no undo |
| force-push, `git branch -D` | rewrites or deletes history others may hold |
| `DROP`, `TRUNCATE`, `DELETE`/`UPDATE` without `WHERE` | table- or every-row data loss |
| database migrations against non-local targets | schema changes on data that matters |
| `terraform destroy`, `kubectl delete`, bucket/volume removal | tears down live infrastructure and the data on it |
| `chmod -R`, `chown -R` | recursive permission damage, hard to reverse |
| `kill` on processes this session didn't start | may take down the user's other work |
| overwriting files that weren't read first | destroys content nobody has seen |
| `>` redirection onto existing files | silent truncation of the target |

## Output format (on activation)

```
# Safety Guardrails: ON

Every command matching the watch table now requires your explicit yes before it runs.
This gate is conversational, not harness-enforced — I re-state it after any compaction.
Deactivate with /careful off.

<the watch table above, verbatim>
```

## Rules

- Warnings must name the specific data at risk ("deletes the 3 uncommitted files under
  src/auth/, not recoverable"), never a generic "this is dangerous."
- The user can override any single warning; record the override in the response
  ("proceeding on explicit override: <command>").
- /careful never silently blocks. Every match surfaces the choice — run, skip, or safer
  alternative — and the user decides.
- Deactivation is explicit only (`/careful off`). Never turn yourself off.
- This guardrail is conversational, not enforced by the harness: after any context
  compaction or summarization, re-state the active guardrail status in your next
  reply. For permanent, deterministic enforcement, use a PreToolUse hook in
  `.claude/settings.json` that pattern-matches the watch table.
