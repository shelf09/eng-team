# claude-eng-team

**Turn Claude Code into a virtual engineering team.** A CEO who challenges whether
the feature should exist, an engineering manager who locks the architecture before
day one, a designer who catches AI slop, a staff reviewer who hunts production bugs,
a QA lead who drives a real browser, a security officer who runs OWASP + STRIDE
audits, and a release engineer who takes the PR all the way to verified-in-production
— plus the SRE, the DBA, the performance engineer, and the rest of the bench.

36 slash commands, 5 subagents, 4 skills. Every one of them is a plain Markdown file.
No binaries, no setup scripts, no browser infrastructure shipped in the box — if you
can read it, you can audit it and fork it. MIT licensed.

Inspired by [Garry Tan's gstack](https://github.com/garrytan/gstack): same philosophy
(a sprint process with specialist roles, artifacts feeding forward), different
constraint (100% Markdown).

This repo ships three collections, each in its own folder under `.claude/`:
**eng-team** (this README — the virtual engineering team),
**[clone-video-creator](clone-video-creator.md)** (a clone studio: brain, image,
voice, and video clones with screening gates), and
**[marketing](marketing.md)** (50 marketing skills, from SEO to webinars).

---

## Quick start

Copy the `.claude/` folder into a project:

```bash
# from the root of your project
cp -r /path/to/claude-eng-team/.claude .
```

Or install globally so every project gets the team:

```bash
mkdir -p ~/.claude/commands ~/.claude/agents ~/.claude/skills
cp -r /path/to/claude-eng-team/.claude/commands/eng-team ~/.claude/commands/
cp -r /path/to/claude-eng-team/.claude/agents/eng-team ~/.claude/agents/
cp -r /path/to/claude-eng-team/.claude/skills/eng-team ~/.claude/skills/
```

Each collection lives in its own folder — `eng-team/` here, plus
[clone-video-creator](clone-video-creator.md) — so collections never collide.
Claude Code versions that namespace by folder invoke these as
`/eng-team:reviewer`; older versions as `/reviewer`. Same files either way.

Then open Claude Code and type a slash command:

```
/eng-team:reviewer                                   → hunt production bugs in the current diff
/eng-team:team add CSV export to the reports page    → run the whole pipeline, idea → shipped PR
```

There is no step three.

## The Sprint

The insight this borrows from gstack: this is a **process**, not a pile of tools.
Each command is a stage in a sprint, and each stage writes an artifact the next
stage reads. You can run the whole thing with `/team`, or run any stage by hand.

**THINK** — figure out what the real problem is.

- `/office-hours` — a YC partner digs for the pain underneath your feature idea. Hypothetical pain doesn't count.
- `/ceo` — challenges whether to build it at all. Verdicts: BUILD / RESHAPE / KILL / PARK.

**PLAN** — turn the idea into something an engineer can execute.

- `/pm` — writes the PRD: personas, user stories, acceptance criteria, an uncomfortably small v1.
- `/em` — locks the architecture and slices the work into shippable tickets.
- `/spec` — turns intent into a precise, executable spec, graded before it files.
- `/autoplan` — one command in, a fully reviewed implementation plan out. Plan only, no code.
- `/adr` — records the decision, its options, and its consequences, so nobody does archaeology in a year.

**BUILD** — write the code, with companions that keep the session honest.

- `/tdd` — implements each ticket test-first: red before green, one vertical slice at a time, behavior tests at agreed seams.
- `/investigate` — systematic root-cause debugging. No edits until the cause is proven.
- `/careful` — session-wide confirmation gate before any destructive command.
- `/freeze` — locks all writes to one directory for the rest of the session.
- `/learn` — records what the team learned into project memory as you go.

**REVIEW** — every angle, before the PR exists.

- `/reviewer` `/designer` `/security` — the core gates (bugs, slop, vulnerabilities).
- `/second-opinion` — an adversarial panel that reads the diff cold from hostile angles.
- `/perf` `/dba` `/a11y` `/sre` — the specialists, when the diff touches their turf.
- `/preflight` — all four core inspectors in parallel, one merged verdict: GO / GO WITH FIXES / NO-GO.

**TEST** — prove it works, with evidence.

- `/qa` — a test plan executed in a real headless browser, screenshots saved.
- `/benchmark` — records a performance baseline or diffs against one. n≥5 runs or it doesn't count.

**SHIP** — get it merged and verified.

- `/release` — runs the gates, writes the changelog, opens the PR.
- `/land` — takes the approved PR from merge to verified-in-production, rollback ready.
- `/docs` — fixes the docs the diff just made into lies.

**OPERATE** — watch it in the wild.

- `/canary` — watches the fresh deploy for a set window: HEALTHY / DEGRADED / FAILING.
- `/sre` — audits operability: when this breaks at 3am, how long until someone knows?

**REFLECT** — close the loop.

- `/retro` — what shipped, what churned, one falsifiable experiment. All from git, zero opinions.
- `/postmortem` — blameless incident reconstruction from repo evidence.
- `/standup` — yesterday / today / blocked, from real repo state.
- `/tech-debt` — finds, prices, and ranks the debt into a payable backlog.
- `/onboard` — explains the codebase to a new engineer, day one to first PR.

### The artifact pipeline

Every pipeline stage writes to `docs/team/<feature-slug>/`, and every later stage
reads what's already there:

```
docs/team/<feature-slug>/
├── design-doc.md            # THINK   (/office-hours, /ceo)
├── prd.md                   # PLAN    (/pm)
├── architecture.md          # PLAN    (/em)
├── spec.md                  # PLAN    (/spec)
├── plan.md                  # PLAN    (/autoplan)
├── mockups/                 # PLAN    (/mockups) — variant boards + winner.html,
│                            #          read by /designer and /design-system
├── qa-report.md             # TEST    (/qa)
└── qa-evidence/             # TEST    (/qa) — screenshots cited by the report

docs/team/benchmark-baseline.md   # TEST (/benchmark) — global baseline, read by /canary
docs/team/LEARNINGS.md            # compounding memory — consulted by every planning
                                  #   and reviewing role; /learn is its sole writer
```

Nothing falls through the cracks, because every step reads what came before.

## See it work

```
you:  /office-hours I want to add a dashboard where users can see all their stats

  partner: What happened the last time a user asked for this? Walk me through it.
  you:     Two users emailed asking why their weekly totals looked wrong.
  partner: Then they don't want a dashboard — they want to trust the numbers they
           already see. That's a data-correctness problem wearing a dashboard's
           clothes. Write that up instead.
  → docs/team/weekly-totals-trust/design-doc.md

you:  /team fix the weekly totals discrepancy and show users how each number is derived

  → CEO: BUILD — cuts "export to PDF" from scope
  → PM → EM → spec → build: 3 tickets implemented test-first, suite green
  → /preflight: reviewer finds a timezone boundary bug; fixed; re-run → GO
  → /qa: 6/6 flows pass in Chromium, evidence in docs/team/weekly-totals-trust/qa-evidence/
  → /release: gates green, changelog written, PR #47 opened

you:  /land 47
  → merged, deploy watched, verified with real requests against production

you:  /canary https://app.example.com 15m
  → HEALTHY — error rate and console output at or better than pre-deploy baseline
```

## The roster

Each command lives in exactly one table below; the "Which review should I use?"
guide re-references them.

### Leadership

| Command | One-liner |
|---------|-----------|
| `/ceo` | Rethinks the product; challenges what you're building before you build it. |
| `/pm` | Turns a fuzzy idea into a PRD with user stories and acceptance criteria. |
| `/em` | Locks the architecture and slices work into shippable tickets. |

### Quality gates

| Command | One-liner |
|---------|-----------|
| `/reviewer` | Hunts production bugs in the diff — races, leaks, broken contracts — not style nits. |
| `/designer` | Reviews UI for AI slop, inconsistency, and generic-template syndrome. |
| `/qa` | Writes a test plan and verifies it in a real browser with screenshots. |
| `/security` | OWASP Top 10 + STRIDE threat-model audit; every claim tied to a file and line. |

### Specialists

| Command | One-liner |
|---------|-----------|
| `/sre` | Audits operability: what happens when this breaks at 3am? |
| `/perf` | Finds the code that will be slow with real-world data — fast with 10 rows, dead with 10,000. |
| `/dba` | Reviews schemas, migrations, and queries before they hurt you; code rolls back, data doesn't. |
| `/a11y` | WCAG 2.2 AA audit of UI code and rendered pages; every finding says who it locks out. |
| `/docs` | Writes or fixes docs that match what the code actually does — docs that lie are worse than none. |

### Shipping & operations

| Command | One-liner |
|---------|-----------|
| `/release` | Runs the gates, writes the changelog, and ships the PR — or refuses and says what's blocking. |
| `/land` | Takes an approved PR from merge to verified-in-production, rollback in hand. |
| `/canary` | Watches a fresh deploy for a set window and calls HEALTHY, DEGRADED, or FAILING. |
| `/benchmark` | Records a performance baseline or diffs against one. Numbers, not vibes. |

### Build

| Command | One-liner |
|---------|-----------|
| `/tdd` | Implements test-first: red before green, vertical slices — a test never seen failing doesn't count. |
| `/investigate` | Systematic root-cause debugging — no edits until the cause is proven with evidence. |

### Safety & memory

| Command | One-liner |
|---------|-----------|
| `/careful` | Session-wide confirmation gate: no destructive command runs until you've seen what it destroys. |
| `/freeze` | Freezes all writes to one directory for the rest of the session. |
| `/unfreeze` | Releases the `/freeze` edit lock and surfaces every edit the freeze deferred. |
| `/learn` | Maintains `docs/team/LEARNINGS.md`, the shared memory the planning and reviewing roles consult. |

### Power tools

| Command | One-liner |
|---------|-----------|
| `/team` | The whole pipeline: product review → plan → build → parallel gates → browser QA → shipped PR. |
| `/autoplan` | One command in, a fully reviewed implementation plan out. Plan only, no code. |
| `/preflight` | Reviewer, designer, security, and QA check the diff in parallel. One verdict. |
| `/second-opinion` | An adversarial panel reads the diff cold; agreement only counts between reviewers who couldn't copy each other. |
| `/office-hours` | A YC partner who digs for the real pain before you build anything. |
| `/spec` | Turns vague intent into a precise, executable spec, graded before it files. |
| `/standup` | What happened, what's next, what's blocked — from real repo state, not memory. |
| `/retro` | What shipped, what churned, and one falsifiable experiment; every line from the repository. |
| `/adr` | Captures a decision, its options, and its consequences. |
| `/tech-debt` | Finds, prices, and ranks the debt into a payable backlog — including what to consciously not fix. |
| `/postmortem` | Blameless postmortem reconstructed from repo evidence: timeline, root cause, real action items. |
| `/onboard` | Explains this codebase to a new engineer, day one to first PR. |
| `/design-system` | Audits what your styles actually do and codifies it into `DESIGN.md`. |
| `/mockups` | Generates structurally different HTML mockups for "I'll know it when I see it." |

## Which review should I use?

| You're building... | Run |
|--------------------|-----|
| Something end users see | `/designer`, then `/qa` |
| Something developers use | `/docs`, then `/onboard` |
| Architecture or a big refactor | `/em`, then `/reviewer` |
| Anything, at the plan stage | `/autoplan` |
| Anything, at the code stage | `/preflight` |

## How it works

Everything lives in `.claude/`, using three native Claude Code features:

```
.claude/
├── commands/    # 36 slash commands — one Markdown file per role or tool
├── agents/      # 5 subagents — /preflight fans out code-reviewer, security-auditor,
│                #   design-critic, qa-tester; /team fans out the first three;
│                #   architect runs out-of-band for architecture second opinions
└── skills/      # 4 reference skills — ai-slop, browser-qa, threat-model, tdd
```

- **Commands** become slash commands automatically. Each file is a role: a persona,
  a process, an output contract, and hard rules. What you type after the command
  flows in via `$ARGUMENTS`.
- **Agents** are subagent definitions, so `/preflight` and `/team` can run their
  inspectors simultaneously on the same diff instead of one at a time.
- **Skills** hold shared reference material — the designer's slop catalogue, QA's
  Playwright discipline, security's STRIDE tables, the TDD discipline every build
  follows — so the knowledge lives in one place and every role cites the same source.

No code runs to make this work. The Markdown is the product.

## Design principles

1. **Every verdict is forced.** No role is allowed to say "both options are valid."
2. **Evidence or it didn't happen.** A file:line, a traced input, a screenshot, a
   measurement — "might be a problem" is banned across the team.
3. **Cleared lists are mandatory.** Auditors report what they checked and found
   clean, so coverage is auditable — not just the hits.
4. **Fixes use what exists.** No role may prescribe a new framework, design system,
   or infrastructure as a "fix."
5. **Honest failure.** QA that can't start the app reports FAIL — it never quietly
   downgrades to a code read and calls it testing.
6. **Artifacts feed forward.** Every stage writes a document the next stage reads;
   the PRD constrains the architecture, the spec constrains QA.
7. **Memory compounds.** Every planning and reviewing role consults
   `docs/team/LEARNINGS.md` before acting, so the team stops repeating last
   month's mistakes.

## Requirements

- [Claude Code](https://claude.com/claude-code) — the only hard requirement.
- Optional, used when present:
  - `git` + the [`gh` CLI](https://cli.github.com/) — for `/release`, `/land`, `/standup`, `/retro`, `/postmortem`
  - [Playwright](https://playwright.dev/) — for `/qa`, `/a11y`, and `/canary` browser
    verification (`npm i -D playwright && npx playwright install chromium`)
  - Your project's own test and lint commands — the gates find and run them

Roles degrade gracefully: without `gh`, `/release` prints the commands for you to
run; without a browser, `/qa` tests your real CLI or API instead and says so.

## Customizing your team

- **Tune a role:** edit its file in `.claude/commands/eng-team/`. Want the reviewer to also
  enforce your error-handling convention? Add a bullet to its hunt list.
- **Hire a specialist:** copy an existing command file and change the persona,
  process, and output contract. An i18n auditor, a licensing checker, a mobile
  reviewer — each is one Markdown file.
- **Change the pipeline:** `/team`'s stages are a list in `team.md`. Reorder, add a
  gate, or remove one.
- **Project knowledge:** put stack, conventions, and commands in your project's
  `CLAUDE.md` — every role reads it automatically.

## FAQ

**Does this replace human review?**
No. It catches what tired humans skip and makes PRs arrive pre-reviewed. Humans
still own judgment, taste, and the merge button.

**Why so opinionated — forced verdicts, banned phrases?**
Because LLM output regresses to agreeable mush without hard constraints. The rules
in each file exist to keep the roles sharp.

**What does it cost to run?**
Your normal Claude Code usage. Single roles are cheap; `/team`, `/preflight`, and
`/second-opinion` spawn parallel subagents and use proportionally more.

**Can I use only part of it?**
Yes. Every file is independent — delete what you don't want and nothing breaks.

**How is this different from gstack?**
Same philosophy: a sprint process with specialist roles and artifacts feeding
forward. Different constraint: gstack ships browsers and binaries; this ships
prompts. Pure Markdown means it's smaller, fully auditable, and forkable with a
text editor.

## License

[MIT](LICENSE) — free to use, modify, and redistribute.
