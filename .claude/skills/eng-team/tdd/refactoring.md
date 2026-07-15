# The Third Step, Done Right

Refactoring inside the TDD loop: change structure, never behavior. SKILL.md owns
the loop; this file deepens its third step. The tests are the safety net *and*
the design feedback — if refactoring is hard, the tests are telling you where the
design is wrong (the coupling red flags live in `tests.md`).

## The contract

1. **Refactor only on all-green.** A refactor started on red mixes "fixing" with
   "restructuring" and you can't tell which change broke what.
2. **Behavior tests survive UNCHANGED.** If you had to edit a test during a
   refactor, that test was implementation-coupled. Fix it as a test bug — and say
   so in the commit — don't quietly rewrite it to match the new internals.
3. **Run the suite after every move**, not once at the end. A refactor is a
   chain of tiny, individually-verified moves; batch verification loses the
   information about which move broke things.
4. **No new behavior sneaks in.** Spotted a missing case mid-refactor? Finish the
   refactor, then write the red test. New behavior always enters through red.
5. **Structural and behavioral changes land in separate commits.** A refactor
   commit proves itself by "tests untouched, suite green"; a behavior commit by
   its red test. A commit that mixes both can be reverted as neither.

## Test code is code — but only one side moves at a time

Suites accumulate duplication too: repeated arrange blocks, copy-pasted object
literals. Extract builders and helpers under the mirror-image contract:
production code frozen, assertions and expected values byte-for-byte intact,
suite green before and after. "Tests survive unchanged" governs refactors of
production code; when it's the tests' turn to be cleaned, production holds
still. Never both in one commit — that is where behavior changes hide.

## What to refactor, in priority order

### 1. Duplication — by the rule of three

First copy is fine. Second copy gets a note. Third copy gets extracted — **but only
when the copies must change together**. Incidental similarity extracted too early
creates false coupling: two callers chained to one helper that now needs flags.

```js
// BAD: two validators that happen to look alike today, welded together
function validateField(value, { isEmail }) {
  if (!value) throw new Error("required");
  if (isEmail && !value.includes("@")) throw new Error("invalid");
  // next requirement: usernames forbid "@" — now the flag forest grows
}

// GOOD: same shape, different reasons to change — keep them separate
function validateEmail(value) { /* email rules evolve with email specs */ }
function validateUsername(value) { /* username rules evolve with product */ }
```

The test for real duplication: if requirement X changes, do ALL copies change? Yes
→ extract. No → the similarity is coincidence; leave it.

### 2. Module deepening — deep modules, small interfaces

Collapse pass-through layers. Pull complexity behind the seam so callers get
simpler. The seam the tests hit stays put; everything behind it is fair game.

```
BEFORE: caller → OrderService.place() → OrderValidator → OrderPersister → db
        (three shallow layers, each a pass-through with one caller)

AFTER:  caller → placeOrder(order)  // validation + persistence inside
        (one deep module; tests at placeOrder() didn't change)
```

### 3. Names — rename toward the domain language

The tests already speak the domain: "user can checkout with valid cart". If the
implementation says `processData(obj)` where the test says "cart", rename until
`grep` for a domain word finds the code that implements it.

## SOLID, pragmatically

Tests are the pressure gauge. A test that's hard to write is the design telling
you something — read the smell off the test file, not off a principles poster.

| Principle | Smell in the tests | Minimal move |
|-----------|-------------------|--------------|
| **S**RP | Test file needs unrelated setup blocks (db + email + pricing) to test one thing | Split the module along the setup boundaries |
| **O**CP | Adding a case means editing a switch AND every test that enumerated the old cases | Extract the varying part; new case = new file + new test |
| **L**SP | Tests for a subtype re-assert the parent's behavior "just to be safe" | Subtype honors the parent's contract, or it isn't a subtype — compose instead |
| **I**SP | Mock setup stubs ten methods to satisfy one call | Split the interface at the usage seam |
| **D**IP | You can't test without mocking your own module | Inject the dependency at the boundary; mock only what's now injected |

## When to STOP

No speculative abstraction: if no current test demands the flexibility, don't
build it. Three concrete stop signs:

1. **Interface with one implementation** and no second in sight — delete the
   interface, keep the class.
2. **Parameter nothing passes** — every call site sends the same value or omits
   it. Remove it; re-add when a test needs it.
3. **Layer that only delegates** — every method is a one-line forward. Collapse it.

The loop's green rule doesn't expire at green: minimum code that solves the
problem — structure no test demands is just new code with no red.

## Refactor smells → moves

| Smell | Move |
|-------|------|
| Long method | Extract until each piece does one thing the tests can name |
| Feature envy — method reads another object's fields more than its own | Move the method to the data it envies |
| Shotgun surgery — one change touches five files | The scattered pieces want to be one module; gather them |
| Primitive obsession — tests keep re-explaining what a string/number means | Introduce the domain type (`Money`, `Email`) the tests keep describing |
