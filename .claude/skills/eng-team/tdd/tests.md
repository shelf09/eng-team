# What Good Tests Look Like

## Anatomy

Arrange → Act → Assert, in that order, no logic between phases:

```js
test("expired coupon is rejected at checkout", async () => {
  // Arrange — build the world
  const cart = createCart([{ price: 20 }]);
  const coupon = createCoupon({ expiresAt: "2020-01-01" });
  // Act — one call to the seam
  const result = await checkout(cart, { coupon });
  // Assert — one outcome
  expect(result.status).toBe("rejected");
  expect(result.reason).toBe("coupon_expired");
});
```

**One logical assertion per test.** Multiple `expect()` lines verifying ONE outcome
(status + reason above) are fine; verifying two behaviors is two tests. If the name needs "and", split it.

**Each test builds its own world.** State one test writes and another reads makes failures
order-dependent — green in the full suite, red run alone. Arrange creates everything, every run.

## Naming

Names state WHAT capability exists, never HOW it's implemented:
- GOOD: `"duplicate email registration returns a conflict error"`
- BAD: `"register calls validateEmail before insertUser"`

The suite read top to bottom is the spec of the module. If a teammate can't learn what it
does from test names alone, the names are wrong. A name no failure could contradict —
`"handles edge cases"`, `"works correctly"` — is not a name.

## Implementation coupling — the red-flag list

| Red flag | Why it kills the test |
|----------|----------------------|
| Testing private/unexported functions | Refactor renames it; behavior unchanged, test dead |
| Asserting mock call counts/args/order | Verifies plumbing, not outcome — the rare exceptions live in `mocking.md` |
| Mocking your own modules | Passes against imagined collaborator behavior |
| Asserting internal state fields | Couples to data layout, not contract |
| Verifying through a side channel | Bypasses the interface the contract promises |

The sneakiest is the side channel — reaching around the seam to check the result:

```js
// BAD: raw SELECT — pins schema, and passes even if getUser can't read it back
test("createUser persists the user", async () => {
  await createUser({ email: "a@b.com" });
  expect(await db.query("SELECT * FROM users WHERE email = 'a@b.com'")).toHaveLength(1);
});
// GOOD: the contract is "created users are retrievable" — read back through the seam
test("created user is retrievable", async () => {
  const { id } = await createUser({ email: "a@b.com" });
  expect((await getUser(id)).email).toBe("a@b.com");
});
```

## Tautological tests

SKILL.md covers the core. Three disguises — all pass by construction, none can disagree with the code:

1. **Recomputing the expected value** — the same reduce/format/sum as the code.
2. **Snapshotting your own output and blessing it** — "expected" is whatever the code said first.
3. **Asserting a constant against itself** — `expect(pool().max).toBe(MAX_CONNECTIONS)` where
   the code sets `max: MAX_CONNECTIONS`: any wrong value passes too. Hard-code the spec's literal.

## Edge cases that earn their keep

| Edge | Ask |
|------|-----|
| Empty collection | Return empty, or throw? |
| Zero / negative numbers | Sign handling, off-by-one |
| Exactly one item | Loops and reducers with degenerate input |
| Duplicates | Dedup or preserve — which does the contract say? |
| Unicode/emoji in strings | Length, slicing, storage round-trip |
| Max/boundary sizes | Accepted at N, rejected at N+1 |
| Already exists | Idempotent, error, or overwrite? |
| Concurrent double-call | Double-submit, double-charge |
| Out-of-order events | Late webhook, stale update |
| Timezone/DST | Date math across offsets |

**Rule: pick edges the SEAM can actually reach.** If upstream validation makes an edge impossible at this interface, testing it here is waste.

## Async and error paths

Await rejections properly — an un-awaited rejection assertion passes vacuously. So does a
`try/catch` with assertions only inside `catch`: when nothing throws, nothing asserts.

```js
await expect(checkout(emptyCart, payment)).rejects.toThrow(EmptyCartError);
```

Test the error CONTRACT — the type, message, or code the caller depends on — not the internal throw site. Every error path in the spec gets a test.

## Table-driven tests

When N inputs share one behavior, use `test.each` with independent expected literals:

```js
test.each([
  [[], 0],
  [[{ price: 10 }, { price: 5 }], 15],
])("calculateTotal(%j) is %i", (items, expected) => {
  expect(calculateTotal(items)).toBe(expected);
});
```

Never generate the expected column in a loop — that is tautology at scale.

## Snapshot rules

- Snapshots ONLY where exact output shape IS the contract: serializers, codegen, wire formats.
- A snapshot nobody read before committing asserts nothing — it blesses output (disguise #2).
- Never snapshot volatile fields (timestamps, ids): every run diffs, everyone `--update`s blindly.
