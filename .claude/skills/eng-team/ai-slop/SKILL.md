---
name: ai-slop
description: Catalogue of AI-generated design and copy slop patterns, with detection heuristics. Use when reviewing UI code, screens, or product copy for generic template aesthetics, inconsistency, and shipped placeholders.
---

# AI Slop Catalogue

"AI slop" is the committee-safe, template-shaped output LLMs produce when nobody
pushes back. One bad choice is a mistake; slop is the absence of choices. This
catalogue lists the recurring patterns and how to detect them mechanically where
possible. Detection commands are starting points — adapt paths and file globs to
the project's stack.

## 1. Visual slop

| Pattern | What it looks like | Detection |
|---------|-------------------|-----------|
| Default-AI palette | Purple/indigo/violet gradients, `#6366f1`-family everywhere | grep stylesheets for `indigo`, `violet`, `purple`, gradient pairs |
| Glassmorphism reflex | `backdrop-blur` + translucent white cards on everything | grep `backdrop-blur`, `bg-white/10` |
| Gradient headline | Transparent text filled with a gradient on the hero title | grep `bg-clip-text`, `text-transparent`, `-webkit-background-clip` |
| Radius uniformity | Every element `rounded-xl`/`rounded-2xl`, including things that shouldn't be | count distinct radius values; 1 value everywhere = slop, 8 values = chaos |
| Typography soup | 3+ font families, 6+ text sizes, or mixed weights for the same role (`font-medium` here, `font-semibold` there on sibling headings) | count distinct families/sizes/weights in use |
| Hero + three cards | Landing layout: centered hero, gradient headline, exactly 3 feature cards with icon-title-blurb | structural read of the page |
| Emoji iconography | 🚀✨🎯 as feature icons or section markers | grep for emoji in JSX/HTML/markdown UI strings |
| Shadow soup | One-off `box-shadow` values per component | count distinct shadow values |
| Center-everything | `text-align: center` / `items-center` on data-dense UI | grep + judgment |
| Token orphans | A color/spacing/radius/font value used exactly once | inventory all values, sort by frequency, inspect the singletons |

**The token inventory is the core move:** grep out every color, spacing, radius,
font-size, and shadow value in the project's styles. A healthy project has a small
set of repeated values. Slop shows up as singletons and near-duplicates
(`#6366f1` and `#6466f0`; `12px` next to a `4/8/16` scale).

```sh
# Raw CSS values by frequency — singletons at the bottom are the suspects
grep -rhoE --exclude-dir=node_modules '#[0-9a-fA-F]{3,8}|[0-9.]+(px|rem)' --include='*.css' --include='*.scss' . | sort | uniq -c | sort -rn
# Tailwind arbitrary values — every hit is a value the project's scale doesn't cover
grep -rhoE --exclude-dir=node_modules '[a-z-]+-\[[^]]+\]' --include='*.tsx' --include='*.jsx' --include='*.vue' --include='*.html' . | sort | uniq -c | sort -rn
```

## 2. Copy slop

| Pattern | Examples | Detection |
|---------|----------|-----------|
| LLM marketing verbs | unlock, empower, elevate, supercharge, streamline, seamless, effortless | grep the strings |
| Rule-of-three taglines | "Fast. Simple. Powerful." / "Build. Ship. Scale." | grep for `\w+\. \w+\. \w+\.` in UI strings |
| Negative parallelism | "It's not just X — it's Y" / "This isn't about A. It's about B." | grep `not just`, `isn't just` in UI strings |
| Shipped placeholders | lorem ipsum, "Your Name", "John Doe", "example@email.com" visible in UI, fake testimonials with stock names | grep: `lorem`, `ipsum`, `John Doe`, `Jane`, `Acme`, `placeholder` in rendered strings |
| Hedge copy | "may", "might", "could" in product claims; "simply" and "just" before hard steps | grep in docs/UI strings |
| Sparkle branding | ✨ next to any feature name, "AI-powered" as a feature | grep `✨`, `AI-powered` |
| Title Case Everything | Headers, Buttons, And Labels All Capitalized Like This | read the strings |

## 3. Interaction slop

- **Missing states:** no empty state, no loading state, no error state — check every
  data-driven view for all three.
- **Focus invisible:** `outline: none` (or Tailwind `focus:outline-none`) without a
  replacement focus style. grep it.
- **All-primary buttons:** every action is a filled primary button; destructive
  actions look identical to safe ones.
- **Dead hover:** interactive elements with no hover/active feedback, or identical
  feedback on all of them.
- **Modal reflex:** modals for confirmation of trivial actions, inline edits, or
  content that should be a page.
- **Toast abuse:** irreversible outcomes announced via auto-dismissing toast.

## 4. Code-level design slop

- Inline style objects duplicating what the design system already provides.
- A new `Button`/`Card`/`Modal` component when one already exists in the project.
- Hardcoded strings/colors in components when a token/i18n system exists.
- CSS classes named `container2`, `newWrapper`, `styles2`.
- `!important` to win specificity fights; `z-index: 9999` to win stacking fights.
- Tailwind arbitrary values (`w-[347px]`, `text-[13px]`) next to a working scale.

## Severity rubric

- **BLOCKER** — placeholders/fake content visible to users; missing error states on
  real flows; focus removed with no replacement.
- **MAJOR** — token inconsistency (off-scale values, orphan colors); missing
  empty/loading states; all-primary actions; marketing slop in product UI.
- **NIT** — taste calls: centering, radius choices, tone. Report honestly as taste.

## The counter-move

Fixes must come from the project's existing vocabulary: its tokens, its components,
its voice. The fix for slop is never "add a new design system" — that's how the slop
got in. If the project has no explicit tokens, the scale still exists implicitly:
the most-frequent values in the inventory *are* the system. Pull outliers toward them.
