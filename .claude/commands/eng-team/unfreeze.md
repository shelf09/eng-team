---
description: Releases the /freeze edit lock and surfaces every edit the lock deferred.
---

# Power Tool: Unlock

You release the write barrier set by /freeze (see freeze.md — this is `/freeze off`
under its own name). Your standard: **a lock never lifts silently — the release names
the boundary that dropped and every edit the freeze deferred.** Blocked work that
vanishes with the lock is work that never happens.

**Arguments:** $ARGUMENTS — /unfreeze takes none; empty releases the active freeze.
If a path was passed and it differs from the frozen boundary, name the directory
that is actually frozen before releasing — the user may be misremembering the lock.

## Process

1. Recall the freeze state from this session: the boundary from the /freeze
   activation, every BLOCKED BY FREEZE report since, and any one-time exceptions
   the user granted.
2. No freeze active: say so in one line and stop — nothing to release. If /careful
   is on, add that it stays on; /unfreeze does not touch it.
3. Freeze active: release it and print the output below. List each BLOCKED BY
   FREEZE edit that was skipped, path and description verbatim from its report —
   those paths are writable now and the user decides which to pick back up.
4. Boundary unrecallable (post-compaction ambiguity): release anyway — the user's
   intent to end unlocked is unambiguous — and say the boundary could not be
   recalled precisely rather than inventing one. Never invert it into "nothing to
   release."

## Output format (on release)

```
# Edit Lock: OFF

Released: <the previously frozen directory>
Exceptions used while frozen: <paths, or "none">
Deferred edits, now unblocked:
- <path> — <one-line description from its BLOCKED BY FREEZE report>
<or "- none — nothing was blocked while the lock was on">

Whole-repo edits are allowed again. Re-freeze with /freeze <dir>.
```

## Rules

- /unfreeze always ends with the session unlocked. When post-compaction state is
  ambiguous, release and say so — never claim "no freeze active" when one might be.
- Every deferred edit names an exact path taken from its BLOCKED BY FREEZE report;
  never paraphrase paths or summarize several reports into "some config changes."
- Unblocked is not approved: no deferred edit is made until the user asks for it.
- The release changes nothing else — /careful stays on if active, and no other
  session behavior resets.
- The release is conversational, like the lock itself: no harness state changes;
  the confirmation in the transcript is the release.
