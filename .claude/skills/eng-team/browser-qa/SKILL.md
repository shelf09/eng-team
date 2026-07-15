---
name: browser-qa
description: Drive a real headless Chromium browser with Playwright for QA — start the app, execute user flows, assert against the DOM, capture screenshot evidence and console errors. Use whenever a change needs verification in a real browser.
---

# Browser QA with Playwright

How to verify user-facing behavior in a real browser, headlessly, with evidence.
Serves `/qa` (user flows), `/designer` (rendered states), and `/a11y`
(accessibility tree, tab order, computed contrast).

## Setup

Reuse before installing:

1. If the repo has its own Playwright setup (`playwright.config.*`,
   `@playwright/test` in package.json), run or extend the project's tests —
   don't build a parallel harness next to one that exists.
2. Otherwise check for an importable runtime from the project root:
   `node -e "console.log(require('playwright/package.json').version)"` or
   `python -c "import playwright"`.
3. Only then install — without touching package.json or the lockfile:

```bash
# Node (--no-save: leave the project's manifest and lockfile alone)
npm i --no-save playwright && npx playwright install chromium
# Python
pip install playwright && playwright install chromium
```

If install fails (no network, no permission), stop and report the degradation the
way the calling command specifies — never substitute a fake browser result.

## Starting the app under test

1. Find the dev command: `package.json` scripts (`dev`, `start`, `serve`), Makefile,
   README, `docker-compose.yml`. Note the port it claims.
2. Start it with the harness's background execution (`run_in_background`) — a bare
   `cmd &` dies when the Bash call ends. Then poll for readiness; never sleep blind:

```bash
# wait for the port (max ~30s); no -f flag — a 404 or 401 at / still means it's up
for i in $(seq 1 30); do curl -s -o /dev/null http://localhost:3000 && break; sleep 1; done
```

3. Record the URL and `git rev-parse HEAD` for the report.
4. **Always kill what you started** when done — the background task and anything it
   spawned that still holds the port.

## Script template (Node)

Write the script inside the project (e.g. `docs/team/<feature-slug>/qa-evidence/case-signin.js`)
so `require('playwright')` resolves against the project's `node_modules` — a script
outside the repo won't find it. Run with `node`; delete scripts after, keep the
screenshots. That directory is where `/qa`'s report expects its evidence; for ad-hoc
runs outside the pipeline, any project-local `qa-evidence/` directory works — say which.

```js
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Evidence: every console message, page error, and failed request
  const log = [];
  page.on('console', m => log.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', e => log.push(`[pageerror] ${e.message}`));
  page.on('requestfailed', r => log.push(`[requestfailed] ${r.url()} ${r.failure()?.errorText}`));

  await page.goto('http://localhost:3000');

  // --- the flow under test: drive the real UI ---
  await page.getByLabel('Email').fill('qa@example.com');
  await page.getByRole('button', { name: 'Sign in' }).click();

  // --- assert against the DOM, not the pixels ---
  await page.waitForSelector('text=Welcome', { timeout: 5000 });
  const url = page.url(); // assert redirects too

  // --- evidence for humans ---
  await page.screenshot({ path: 'docs/team/<feature-slug>/qa-evidence/signin-success.png', fullPage: true });

  console.log(JSON.stringify({ url, log }, null, 2));
  await browser.close();
})().catch(e => { console.error('CASE FAILED:', e.message); process.exit(1); });
```

Python equivalent: `from playwright.sync_api import sync_playwright` — same structure.

## Rules of evidence

- **The DOM is the oracle; screenshots are for humans.** Assert on text content,
  element state, and URL. Screenshot at each assertion point into the evidence
  directory next to the report that will cite it.
- **Console output is part of the result.** An error or warning during a passing
  flow is a finding — report it.
- **One script per test case** (or clearly separated cases) so a failure names the
  case, not the batch.
- **Failures must fail loudly.** Exit nonzero, print which case and which step.

## Edge-case moves

- Double-submit: `await btn.click(); await btn.click({ force: true, timeout: 1000 }).catch(() => {});`
  then assert exactly one side effect. (Don't `Promise.all` two clicks — if the app
  correctly disables the button, the second click blocks on actionability and fails
  the case for correct behavior.)
- Refresh mid-flow: `page.reload()` between steps; assert state survives (or fails
  cleanly).
- Slow network: `await page.route('**/*', async r => { await new Promise(res => setTimeout(res, 500)); await r.continue(); });`
  — the handler must await the delay and the continue; a bare `setTimeout(() => r.continue(), 500)`
  returns before the route is handled and fails on strict Playwright versions.
- Mobile viewport: `browser.newPage({ viewport: { width: 390, height: 844 } })`.
- Back button: `page.goBack()` after a mutation; assert no duplicate action.

## Rendered checks for design and a11y review

The same harness answers what source code can't — for `/designer` and `/a11y`:

```js
// Viewport sweep: screenshot at desktop default, then mobile
await page.setViewportSize({ width: 375, height: 812 });

// Hover and focus states: force the state, then screenshot it
await page.getByRole('button', { name: 'Save' }).hover();
await page.getByLabel('Email').focus();

// Accessibility tree of a region (Playwright >= 1.49)
console.log(await page.locator('main').ariaSnapshot());

// Tab-order walk: where focus goes, and whether it's visible
for (let i = 0; i < 15; i++) {
  await page.keyboard.press('Tab');
  console.log(await page.evaluate(() => {
    const el = document.activeElement, s = getComputedStyle(el);
    return `${el.tagName}#${el.id || '?'} outline=${s.outlineStyle} ${s.outlineWidth}`;
  }));
}

// Computed colors for contrast math — resolves CSS variables and themes
console.log(await page.locator('.btn').evaluate(el => {
  const s = getComputedStyle(el);
  return { color: s.color, background: s.backgroundColor, fontSize: s.fontSize };
}));
```

## When there's no UI

Same discipline against the real interface that exists: CLI via actual invocations
(assert exit code + stdout), HTTP APIs via `curl` (assert status + body). Plan,
execute, evidence — and state explicitly that a browser wasn't applicable.
