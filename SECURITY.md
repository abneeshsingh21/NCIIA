# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| `1.x` (latest) | ✅ Active security fixes |
| `< 1.0` | ❌ End of life |

---

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

### Preferred: GitHub Security Advisories

Use GitHub's private vulnerability reporting:
👉 [Report a vulnerability](../../security/advisories/new)

This creates an encrypted, private thread between you and the maintainers.

### Alternative: Email

Send a PGP-encrypted email to **security@nciia.dev**

```
PGP Fingerprint: (Add your PGP fingerprint here when publishing)
```

### What to Include

Please provide as much detail as possible:

- **Affected component:** `nciia-core` / `nciia-dashboard` / `nciia-perf`
- **Vulnerability type:** e.g., SQL injection, SSRF, path traversal, RCE, auth bypass
- **Affected versions:** Which version(s) are affected?
- **Reproduction steps:** Minimal, clear steps to reproduce
- **Impact assessment:** What can an attacker achieve?
- **Suggested fix** (optional but appreciated)
- **CVE number** (if you have already requested one)

---

## Response Timeline

| Step | Timeframe |
|------|-----------|
| Initial acknowledgement | Within **48 hours** |
| Severity assessment | Within **5 business days** |
| Fix development begins | Within **7 days** (critical) / **30 days** (high) |
| Patch released | Within **30 days** (critical) / **90 days** (high/medium) |
| Public disclosure | After patch is released + **7-day grace period** |

We follow a **90-day responsible disclosure** policy. If we cannot fix the issue within 90 days, we will notify you and coordinate an appropriate disclosure date.

---

## Severity Classification

We use the [CVSS v3.1](https://www.first.org/cvss/) scoring system:

| Score | Severity | Response |
|-------|----------|----------|
| 9.0–10.0 | 🔴 Critical | Emergency patch within 24-48h |
| 7.0–8.9 | 🟠 High | Fix within 7 days |
| 4.0–6.9 | 🟡 Medium | Fix within 30 days |
| 0.1–3.9 | 🟢 Low | Fix in next release |

---

## Scope

### In Scope

- Authentication and authorisation bypasses
- API key leakage or exposure
- SQL injection / database attacks
- Server-Side Request Forgery (SSRF) in enrichment engine
- Remote Code Execution (RCE)
- Sensitive data exposure (IOC data, case files, persona data)
- Cross-Site Scripting (XSS) in the dashboard
- Dependency vulnerabilities with known exploits (`pip audit`, `npm audit`)
- C++ memory safety issues (buffer overflows, use-after-free in FFI layer)

### Out of Scope

- Vulnerabilities requiring physical access to the server
- Social engineering attacks against maintainers
- Denial-of-service via resource exhaustion (unless trivially exploitable)
- Issues in third-party APIs (VirusTotal, AbuseIPDB, etc.) — report those to the respective vendor
- Findings from automated scanners without proof-of-concept

---

## Security Architecture Notes

Key security controls in N-CIIA:

- **API key authentication** — optional `X-API-Key` middleware on all routes
- **Rate limiting** — sliding-window rate limiter (configurable via env)
- **X-Request-ID tracing** — every request tagged for audit log correlation
- **Strict CORS** — no wildcard origins; explicit allow-list required
- **FFI safety** — all C++ exported functions are `noexcept` with full exception catching
- **No secrets in code** — all credentials loaded from environment variables
- **Structured logging** — `structlog` JSON format; no PII or credentials in log output
- **Dependency pinning** — `pyproject.toml` and `package-lock.json` pin all deps

---

## Credit

Security researchers who responsibly disclose vulnerabilities will be:
- Credited in the release notes (unless they prefer anonymity)
- Listed in the `SECURITY_HALL_OF_FAME.md` (coming soon)

We do not currently offer a monetary bug bounty, but we deeply appreciate responsible disclosure.
