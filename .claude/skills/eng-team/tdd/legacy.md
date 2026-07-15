# TDD Where No Tests Exist

Brownfield changes and bug fixes. SKILL.md states the rule — pin current behavior
before changing untested code; this file is the how: characterization tests, the
bug-fix loop, and the minimal edits that create seams in code that resists testing.

## The net rule

**Never change untested code without pinning its current behavior first.** The
sequence is fixed: pin current behavior → watch the pins pass → make the change →
watch them still pass (or go deliberately red because the behavior change was the
point). Scope the net to the blast radius of your change — pin the paths your edit
can affect, not the whole module. The only edit allowed outside the net is the
smallest possible seam introduction (below).

## Characterization tests

A characterization test pins what the code does **today** — including the weird
parts. Call the seam with representative inputs and assert what it ACTUALLY
returns. Run the code to find the expected value; never guess it. If the answer
is odd, pin the oddity and label it:

```js
// BAD: asserts what the author thinks it should return — guessed, never ran
test("computes shipping for empty cart", () => {
  expect(computeShipping([])).toBe(0);
});

// GOOD: asserts what it demonstrably does — ran it, got NaN, pinned NaN
test("computes shipping for empty cart", () => {
  // documents current behavior; change deliberately
  expect(computeShipping([])).toBeNaN();
});
```

The BAD version fails on day one and tempts you to "fix" code you don't understand
yet. The GOOD version is green immediately and turns red the moment a refactor
changes behavior — which is its entire job. This is the one legitimate exception
to "watch it fail first": a characterization test is green by design, and its red
comes later, when behavior changes on purpose. When you eventually fix the NaN,
you update this test in the same commit, deliberately, and the comment comes off.

## Bug-fix TDD

Every bug fix runs the regression-first loop:

1. **Reproduce the bug with a failing test** at the nearest public seam. This is
   the red. Root-cause discipline lives in `/investigate` — no fix without a
   demonstrated cause.
2. **Watch it fail for the bug's reason.** A test that fails from a typo or a
   missing import proves nothing; the failure message must show the bug.
3. **Fix minimally.** Nothing the failing test doesn't demand.
4. **Watch it pass** — and the rest of the suite stay green.
5. **The test stays forever.** It is now the regression guard for this bug.
   Never delete it because "the bug is fixed"; that is exactly why it exists.

If you can't write the failing test, you don't understand the bug yet. Go back to
step 1, not forward to a fix.

## Finding seams in tangled code

Legacy code resists testing because its dependencies are hardwired. Three moves,
cheapest first:

- **Sprout method/class** — new behavior goes into a new, fully tested unit; the
  old code gains one call into it. The tangle stays untouched; the new code is
  born under test.
- **Extract-and-test** — pull part of the tangle behind an interface, then
  characterize the extracted unit through that interface. Now there is a seam
  with a net.
- **Wrap-and-choke** — put a tested wrapper in front of the old path. New callers
  go through the wrapper; old call sites migrate one at a time until the raw
  path retires.

**Rule: introduce the seam with the SMALLEST possible untested edit** — one
extracted function, one injected parameter — so that everything after the edit
happens under test. The untested window must fit in a single reviewable diff hunk.

## Dependency-breaking quick table

| Hardwired dependency | The minimal break |
|----------------------|-------------------|
| Database client constructed inline | Parameterize the constructor — accept a client, default to the real one |
| Network calls via global `fetch`/SDK | Extract a client behind an interface (`api.getUser(id)`), inject it |
| `Date.now()` / `new Date()` scattered | Inject a clock (`{ now: () => Date.now() }`); pass a fixed one in tests |
| Singleton reached via import | Accept an instance parameter; the singleton becomes the default argument |

Each break is one edit. Resist the rewrite — the goal is a seam, not a new
architecture. What to inject once the seam exists: `mocking.md`.

## Coverage honesty

Characterization coverage is scaffolding, not achievement. It proves you
**preserved** behavior, not that the behavior is **right** — a suite that pins
`computeShipping([]) === NaN` is 100% covered and 100% wrong. Never report legacy
coverage numbers as if they were spec coverage; say which is which.

Mark characterization tests so future readers know their epistemic status: the
`// documents current behavior; change deliberately` comment, a
`describe("characterization: ...")` block, or a file naming convention
(`*.char.test.ts`). A pinned oddity without a label reads like a spec, and the
next engineer will defend the bug.
