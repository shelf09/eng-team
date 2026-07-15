---
name: threat-model
description: STRIDE threat-modeling method and OWASP Top 10 code-audit checklist for defensive security reviews. Use when auditing code, diffs, or architectures for vulnerabilities and missing mitigations.
---

# Threat Modeling: STRIDE + OWASP

Defensive methodology: find weaknesses so they get fixed. Findings and remediations,
never working exploit payloads.

## Step 1 — Draw the surface

Before any checklist, answer three questions with file references:

1. **Entry points** — every place untrusted data enters: HTTP routes, CLI args, env
   vars, file uploads, webhooks, queue consumers, third-party API responses.
2. **Trust boundaries** — where data crosses from less-trusted to more-trusted:
   browser→server, service→database, app→shell, tenant→tenant.
3. **Assets** — what an attacker wants *here*: credentials, PII, tokens, money
   paths, compute, or just a pivot.

## Step 2 — STRIDE each boundary

For every trust boundary, walk all six. Record a threat **or** the mitigation with
its file:line — "we didn't look" and "it's fine" must be distinguishable. When
boundaries are many, take them in asset order: auth/session first, then money and
PII paths, then tenant isolation, then the rest.

| Letter | Threat | The question to ask |
|--------|--------|---------------------|
| **S**poofing | Fake identity | How does this side *know* who's calling? Can the check be skipped or replayed? |
| **T**ampering | Modified data | Is data validated *after* crossing, or only before? Integrity-checked in transit/at rest? |
| **R**epudiation | Deniable actions | If a user disputes an action, what log proves it? Are logs attacker-writable? |
| **I**nfo disclosure | Data leaks | What do error messages, logs, timing, and response differences reveal? |
| **D**enial of service | Exhaustion | What's unbounded: request size, rate, query cost, file size, recursion? |
| **E**levation | Privilege gain | Where is authorization checked — every path, or just the front door? |

## Step 3 — OWASP Top 10 code sweep

Grep for sinks first, then read the path from input to sink.

| Class | What to grep/read for |
|-------|----------------------|
| A01 Broken Access Control | Routes without auth middleware; object IDs from user input used without ownership checks (IDOR); role checks in UI only |
| A02 Crypto Failures | `md5`, `sha1` for passwords; homemade crypto; secrets in code; HTTP where HTTPS is assumed; missing encryption on sensitive columns |
| A03 Injection | String-built SQL (`+`, f-strings, template literals in queries); `exec`/`eval`/`child_process` with user input; raw HTML sinks (`innerHTML`, `dangerouslySetInnerHTML`); path concat for file access |
| A04 Insecure Design | Missing rate limits on auth/expensive ops; trust-the-client patterns; recovery flows weaker than login |
| A05 Misconfiguration | Debug mode flags; permissive CORS (`*` with credentials); default creds; verbose error pages; missing security headers; session cookies without HttpOnly/Secure/SameSite |
| A06 Vulnerable Components | Run the audit tool matching the lockfile (table in Step 4); deps pinned?; deps unmaintained? |
| A07 Auth Failures | Missing brute-force protection; session fixation; tokens that never expire; password rules absent; JWT `alg:none`/unverified |
| A08 Integrity Failures | Unsigned updates/webhooks; `pickle`/unsafe deserialization of external data; CI pulling unpinned scripts |
| A09 Logging Failures | Auth events unlogged; secrets/PII *in* logs; no failure alerting path |
| A10 SSRF | User-supplied URLs fetched server-side; redirects followed blindly; no allowlist for outbound targets |

## Step 4 — Mechanical passes

**Secrets.** Use `git grep` — it scans only tracked files, so `.gitignore` keeps
node_modules and vendor trees out. Quote git pathspecs so git expands them, not
the shell.

```bash
# Hardcoded secrets: names assigned to string literals (high signal; loosen if empty)
git grep -nIiE "(api[_-]?key|secret|passw(or)?d|token)['\"]?[[:space:]]*[:=][[:space:]]*['\"][^'\"]{8,}" \
  -- ':!*.lock' ':!*.min.*'

# Private keys and tracked env files — any hit is a finding
git grep -lI "BEGIN [A-Z ]*PRIVATE KEY"; git ls-files -- '*.env*' '*.pem' '*.key'

# Secrets committed to history of suspicious files
git log -p -- '.env*' '*config*' | grep -iE "key|secret|token" | head -40
```

**Dependencies.** Run the tool that matches the lockfile. Never chain with `||`:
`npm audit` exits nonzero when it *finds* vulnerabilities, which would fall
through to the wrong ecosystem's tool.

| Lockfile | Tool |
|----------|------|
| package-lock.json / yarn.lock / pnpm-lock.yaml | `npm audit` / `yarn npm audit` / `pnpm audit` |
| requirements*.txt / poetry.lock / uv.lock | `pip-audit` |
| Cargo.lock | `cargo audit` |
| Gemfile.lock | `bundle audit` |
| go.sum | `govulncheck ./...` |
| composer.lock | `composer audit` |

No lockfile, or audit tool not installed: A06 goes in **Not tested**, never Cleared.

## Verification discipline

A finding is real only if the path is traced: **source (untrusted input) → flow →
sink**, with no sanitizer/validator on the way. Check for the guard before writing
the finding — frameworks often mitigate by default (parameterized ORMs, template
auto-escaping). Note *which* default saved them, so nobody removes it blindly.

## Severity rubric

- **CRITICAL** — unauthenticated attacker gets data/exec/lateral movement.
- **HIGH** — authenticated user crosses a boundary (IDOR, privilege escalation).
- **MEDIUM** — exploitable with preconditions; or systemic weakness (no rate limits).
- **LOW** — hardening gaps, info leaks with no direct path.

Severity = exploitability × impact. A scary category with no traced path is LOW or
not a finding at all.
