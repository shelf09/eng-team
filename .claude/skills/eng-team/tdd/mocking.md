# Test Doubles Without Lies

Every double is a claim: "the real thing behaves like this." A double that lies —
standing in for code you own, or encoding behavior the real dependency doesn't
have — produces passing tests over a broken system. SKILL.md sets the boundary
rule; this file is the taxonomy and the patterns for obeying it without lying.

## Taxonomy — five doubles, one honest job each

| Double | What it does | Legitimate when | Overuse failure mode |
|--------|--------------|-----------------|----------------------|
| **Dummy** | Fills a parameter, never used | The argument is irrelevant to the behavior under test | Several dummies per call — the function takes dependencies it doesn't use (the ISP smell in `refactoring.md`) |
| **Stub** | Returns canned values, records nothing | Supplying the boundary input the test needs (`clock.now()` → fixed instant) | Stubbing internals to dodge "hard" setup — the real path is no longer exercised |
| **Fake** | Working lightweight implementation (in-memory repo) | Owned infrastructure behind a defined interface | The fake drifts from real behavior and nothing contract-tests it — see below |
| **Spy** | Passes through (or stubs) and records calls | Verifying a side effect invisible through any seam (email actually sent) | Asserting calls whose effect is already observable through the seam |
| **Mock** | Pre-programmed expectations, fails on deviation | Rarely — a boundary where the *call itself* is the contract (audit log, webhook) | Asserting call order/counts/arguments = implementation coupling; refactors break tests with behavior unchanged |

## Prefer fakes for infrastructure you own

One in-memory fake gives every test the same real behavior; a per-test mock db
client re-encodes the implementation in each test. A real test database (SQLite,
testcontainers) beats both when it's cheap to run.

```js
// GOOD: one fake with real behavior — the test reads like a spec
const repo = createInMemoryUserRepo();
test("registered user is findable by email", async () => {
  await registerUser(repo, { email: "a@b.com" });
  expect(await repo.findByEmail("a@b.com")).toMatchObject({ email: "a@b.com" });
});

// BAD: asserts the SQL — pins schema and query shape, proves nothing about behavior
const db = { query: jest.fn().mockResolvedValue({ rows: [] }) };
await registerUser(db, { email: "a@b.com" });
expect(db.query).toHaveBeenCalledWith("INSERT INTO users (email) VALUES ($1)", ["a@b.com"]);
```

**A fake earns trust through a contract suite.** Write one set of tests against the
interface and run it twice — against the fake in the unit tier, against the real
adapter in the integration tier. When the real one changes and the fake doesn't,
the contract suite catches the drift; without it the fake decays into fiction.

## Taming time and randomness

Nondeterminism is a dependency. Inject it like one.

```js
// GOOD: clock injected — the test hands in a fixed one
const isExpired = (session, clock) => session.expiresAt <= clock.now();
test("session is expired exactly at expiresAt", () => {
  expect(isExpired({ expiresAt: 1000 }, { now: () => 1000 })).toBe(true);
});

// BAD: Date.now() buried inside — the test must sleep and hope
const isExpiredBad = (session) => session.expiresAt <= Date.now();
test("session expires", async () => {
  const session = { expiresAt: Date.now() + 50 };
  await new Promise((r) => setTimeout(r, 60)); // flaky under load
  expect(isExpiredBad(session)).toBe(true);
});
```

- **Clocks** — inject `now()`; never assert against a real timestamp.
- **Timers** — for debounce/timeout/retry logic, use fake timers
  (`jest.useFakeTimers()` / `vi.useFakeTimers()`) and advance time explicitly;
  never sleep.
- **RNG / UUIDs** — inject the generator; test with a fixed seed and fixed ids.
- **Host timezone and locale** — date formatting that passes locally and fails in
  CI is leaking `TZ`/locale; pin them in the test environment (`TZ=UTC`) and test
  offset handling with explicit zones.
- A flaky test is a nondeterministic dependency you haven't injected yet. Inject
  it; never add retries or widen tolerances.

## Designing boundaries for mockability

Doubles are only cheap when the boundary was designed for them:

- **Dependency injection** — pass external clients in. A client constructed inside
  the function can only be doubled by module-patching, which welds tests to file
  layout and import order.
- **Domain-shaped seams** — the boundary speaks your domain, not the provider's
  transport. A domain seam is one line to fake; a transport seam makes every fake
  re-implement provider routing.

```js
// GOOD: the seam speaks the domain — one method, one fake line
const api = { getUser: async (id) => ({ id, email: "a@b.com" }) };

// BAD: the seam is a URL router — the fake re-encodes the provider's paths
const badApi = {
  fetch: async (path) => (path.startsWith("/users") ? { id: "u1" } : { id: "o1" }),
};
```

Dependencies already hardwired into existing code: `legacy.md`'s dependency-breaking
table has the minimal seam-introducing edits.

## Network and third-party APIs

Fake at **your wrapper seam**, not the transport. Mocking `global.fetch` welds
tests to URLs, headers, and retry behavior; switching HTTP libraries breaks every
test with behavior unchanged.

```js
// GOOD: double the wrapper you own
const payments = { chargeCard: async () => ({ status: "succeeded", id: "ch_1" }) };
test("order confirms when the charge succeeds", async () =>
  expect((await placeOrder(cart, payments)).status).toBe("confirmed"));

// BAD: doubles the transport — knows the provider's URL, auth header, body shape
global.fetch = jest.fn().mockResolvedValue(new Response(JSON.stringify({ status: "succeeded" })));
```

The wrapper itself still needs proof it speaks the real protocol: contract-check it
against recorded real responses in one thin integration test — the only place
transport details belong.

## The two-doubles smell

If a test needs more than ~2 doubles, the code under test has too many dependencies.
That is a design finding, not a test problem: extract the pure logic into a function
that needs no doubles, or deepen the module so callers see one boundary instead of
five — `refactoring.md` has the moves.
