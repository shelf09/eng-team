---
name: tdd
description: Test-driven development discipline for the BUILD stage — red-green-refactor in vertical slices, behavior-focused tests at agreed seams, test doubles without lies, brownfield and bug-fix TDD. Consult whenever implementing features or fixes test-first.
---

# Test-Driven Development

The red → green → refactor loop, run so it produces tests worth keeping. Adapted
and extended from [mattpocock/skills](https://github.com/mattpocock/skills)
(`engineering/tdd`). Examples here and in the companions are JS; the discipline is
stack-agnostic — translate the idioms to whatever runner the project already has.

This file is the loop and its doctrine. The depth lives in four companions —
consult them at the moment their topic arises, not after:

| File | What it covers | Reach for it when |
|------|----------------|-------------------|
| [tests.md](tests.md) | Test anatomy, naming, coupling red flags, edge-case checklist, async/error paths, table-driven tests, snapshot rules | Writing or judging any test |
| [mocking.md](mocking.md) | Test-double taxonomy, fakes vs mocks, taming time/randomness, designing boundaries for mockability | A test needs a double, or the code fights being tested |
| [legacy.md](legacy.md) | Characterization tests, bug-fix TDD, finding seams in untested code, dependency breaking | The code you must change has no tests |
| [refactoring.md](refactoring.md) | The third step: duplication, module deepening, SOLID as a pressure gauge, when to stop | Everything is green and the code wants cleaning |

## What a good test is

Tests verify **behavior through public interfaces**, not implementation details.
Code can change entirely; tests shouldn't. A good test reads like a specification —
"user can checkout with valid cart" tells you exactly what capability exists — and
survives refactors because it doesn't care about internal structure.

```js
// GOOD: observable behavior through the public API
test("user can checkout with valid cart", async () => {
  const cart = createCart();
  cart.add(product);
  const result = await checkout(cart, paymentMethod);
  expect(result.status).toBe("confirmed");
});

// BAD: coupled to internals — breaks on refactor with behavior unchanged
test("checkout calls paymentService.process", async () => {
  const mockPayment = { process: jest.fn().mockResolvedValue({ status: "confirmed" }) };
  await checkout(cart, mockPayment);
  expect(mockPayment.process).toHaveBeenCalledWith(cart.total);
});
```

The tell for a bad test: it breaks when you refactor, but behavior hasn't changed.
The full red-flag list, naming rules, and edge-case checklist: [tests.md](tests.md).

## Seams — where tests go

A **seam** is the public boundary you test at: the interface where behavior is
observable without reaching inside. Tests live at seams, never against internals.

**Agree the seams before writing any test.** List the seams under test and confirm
them — with the user, or against the acceptance criteria in
`docs/team/<feature-slug>/spec.md` / `prd.md` when the pipeline produced them. You
can't test everything; agreeing seams up front puts the effort on critical paths
and complex logic instead of every getter.

## Plan before the first test

Three questions, answered before red #1 — five minutes here saves rewriting the
suite later:

1. **What interfaces change?** New function, new endpoint, changed signature?
   Confirm the shape with the user or the spec — tests written against a guessed
   interface get thrown away with it.
2. **Which behaviors, in what order?** List them; critical path first, edge cases
   after. Each behavior in `spec.md` becomes one slice of the loop.
3. **Is the code testable as designed?** Nondeterminism (time, randomness) and
   external clients must be injectable, or every test will fight the design —
   see [mocking.md](mocking.md) for the patterns. Fix testability *in the design*,
   not with heroic test setup.

## The loop

1. **Red** — write ONE failing test for the next behavior. Run it. **Watch it
   fail** — and check it fails for the right reason (missing behavior, not a typo).
   A red you never observed is not a red; it might be passing vacuously.
2. **Green** — write the minimum code that makes it pass. Even a hard-coded return
   is legitimate; the next test forces the generalization. No speculative features,
   no anticipating the next test. Run it. Watch it pass.
3. **Repeat** — next slice. One seam, one test, one minimal implementation per cycle.
4. **Refactor only when everything is green** — and behavior tests survive
   **unchanged**; if one breaks, it was implementation-coupled — fix the test, not
   the design. What to clean and when to stop: [refactoring.md](refactoring.md).

**Vertical slices, never horizontal.** Do NOT write all tests first and then all
code. Bulk-written tests verify *imagined* behavior and lock you into a test
structure before you understand the implementation. Each test is a tracer bullet
aimed with what the last cycle taught you.

**Keep the loop seconds long.** Inside the loop, run only the test file you're in;
run the full suite at the end of each slice and before any refactor. A loop that
takes minutes gets abandoned mid-feature — if a single test is slow, that's the
first problem to fix.

## Tautological tests — the silent killer

A test whose expected value is computed the way the code computes it passes by
construction and can never disagree with the code:

```js
// BAD: expected value recomputed like the implementation
const expected = items.reduce((sum, i) => sum + i.price, 0);
expect(calculateTotal(items)).toBe(expected);

// GOOD: expected value is an independent, known literal
expect(calculateTotal([{ price: 10 }, { price: 5 }])).toBe(15);
```

Expected values come from an independent source of truth: a known-good literal, a
worked example, the spec. Never from re-running the algorithm under test. The three
disguises this takes: [tests.md](tests.md).

## Mocking — the boundary rule

Mock at **system boundaries only**: external APIs, time, randomness, sometimes the
filesystem and database. Never mock your own classes, modules, or internal
collaborators — every internal mock welds the test to the implementation. Prefer
fakes for infrastructure you own, and a real test database when it's cheap. The
taxonomy, the time/randomness patterns, and boundary design: [mocking.md](mocking.md).

## Bug fixes and untested code

- **Bug fix?** The reproduction IS the red: write a failing test at the nearest
  public seam that fails for the bug's reason, then fix minimally. Root-cause
  discipline first — the `/investigate` command's iron law applies: no fix without
  a demonstrated cause.
- **No tests at all?** Pin current behavior with characterization tests before
  changing anything — changing untested code without a net isn't TDD, it's hope.
  The moves (sprout, extract-and-test, dependency breaking): [legacy.md](legacy.md).

## Where TDD doesn't apply

Honesty about scope beats dogma:

- **Throwaway spikes** — exploring an API or an idea? Spike without tests, learn,
  **delete the spike**, then TDD the real implementation. The spike must not be
  promoted to production code.
- **Pure configuration and markup** — config files and static content get verified
  by the system tests that consume them, not unit-tested line by line.
- **Generated code** — don't test the output; test the generator.

Everything else that ships gets the loop.

## Definition of done for a slice

- The test was observed red (for the right reason), then green.
- It asserts behavior at an agreed seam, with an independent expected value.
- The implementation contains nothing the current tests don't demand.
- The full suite is green — not just the new test — and no behavior test was
  edited to get there.
