# Product Review: claude-eng-team (the repo as a product)

*Stub created by /ceo — full design docs are /office-hours' job.*

## CEO Verdict

**RESHAPE** — the eng-team prompt pack is a real product with a real wedge, but it
is currently packaged inside a personal workbench. One repo, one customer: keep
claude-eng-team as the Markdown-only virtual engineering team it claims to be
(README:3, README:275); move clone-video-creator (plus tools/cartoon-pipeline and
all demo MP4s), the marketing pack, and the resume skills into their own homes;
commit the actual product — today ~everything but the initial `.claude/` drop is
untracked (git log: 1 commit; git status: 20 untracked paths, ~66MB of binaries).

Scope changes:
- CUT from this repo: clone-video-creator collection, marketing collection,
  resume-* skills, docs/clone/ (26MB), dilbert_*.mp4 (40MB at root), .venv/.
- KEEP: .claude/{commands,agents,skills}/eng-team, README (trim to one
  collection), LICENSE.
- ADD (the only new work authorized): one committed, real `docs/team/<slug>/`
  artifact trail produced by actually running the pipeline — the "See it work"
  section (README:140-165) must become evidence, not fiction.
