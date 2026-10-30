# Design: web admin login

> **Status: draft.** Choices marked *proposed* are recommendations awaiting a decision.

## Context

- The panel can delete events and change the tag library and settings for the whole instance.
- `dishlist.kaotic.cc` runs on FastAPI Cloud. A test there showed that a forged `X-Forwarded-For` value became the client IP the app sees.
- Operators may have no CLI, so nothing here may require one.
- Email is optional, so nothing here may require it either.
- The app can run several instances at once, and rate limits are held in memory per process.

## Goals and non-goals

**Goals:** safe setup using only environment variables and logs; recovery without a CLI; no password stored in environment variables; no effect on hosts and guests.

**Non-goals:** multiple admins or roles, accounts for hosts or guests, two-factor login, `/metrics` authentication.

## Decisions

1. **Temporary password in logs (decided).** The operator rejected setting a password in variables, and a CLI-generated password because hosted operators have no CLI.
2. **Email recovery with a variable-based fallback (proposed).** Email is the easier path but is optional, so a fallback must exist.
3. **Recovery address from `ADMIN_EMAIL` (proposed).** If it were editable in the app, a stolen password could redirect recovery to another inbox.
4. **Login replaces the IP allowlist when enabled (proposed).** The allowlist adds little where IPs can be forged, and a changing home IP would lock the operator out.
5. **Basic Auth (proposed).** It needs no sessions or cookies. See risk R6 and open question 2.
6. **scrypt from the standard library (proposed).** It adds no dependency.

## Risks

Severity reflects the impact on a public instance before mitigation.

| # | Risk | Severity | Mitigation | What remains |
|---|---|---|---|---|
| R1 | **The panel becomes internet-facing.** It previously did not appear to exist for outsiders, and a single password now protects instance-wide destructive actions. | High | Off by default; long-password rule; failed-login limit | This is the core tradeoff and reverses part of ADR-0002 |
| R2 | **Temporary password exposed in logs.** Anyone who can read logs, including log forwarding tools or the platform, can use it until it is replaced, and could claim the panel first. | High | One-time logging; 24-hour expiry; forced change; emailing a setup link instead when possible | If someone claims it first, the operator is locked out and must reset, with no record of what they did |
| R3 | **Inbox compromise means admin compromise.** Anyone with access to `ADMIN_EMAIL` can reset the password. | High | One-hour, single-use links; alert email on change | Accepted if the inbox is trusted; the security of the panel depends on it |
| R4 | **Reset link poisoning.** A link built from the request's `Host` header could point to an attacker's site and leak the token. | High | Links only use `PUBLIC_BASE_URL`; recovery is off without it | None if the rule is kept |
| R5 | **Cross-site form submission.** Browsers resend Basic Auth automatically, so another site could submit admin forms while the operator is logged in. | High | Origin check on all admin POST routes | Relies on the proxy preserving `Host`; a proxy that rewrites it would break admin forms (see R13) |
| R6 | **Basic Auth limits.** There is no real logout, the password is sent with each request, and it can remain usable on a shared computer until the browser closes. | Medium | HTTPS required; documented behaviour | Remains unless a session-based login is chosen |
| R7 | **Password guessing.** The operator chooses the password, and forged IPs make per-IP limits useless. | Medium | Minimum length; global failed-login limit | No check against known breached passwords |
| R8 | **Lockout through the failed-login limit.** The limit is global, so an attacker can repeatedly block the real operator from the web panel. | Medium | Short window | Accepted: nuisance rather than compromise, but no way around it during an attack |
| R9 | **Limits are per process and reset on restart.** Autoscaling multiplies the real limit, and redeploys clear it. | Medium | Strong password hashing | A shared, database-backed counter would close this at the cost of more writes |
| R10 | **Recovery email abuse.** Anyone can trigger reset emails, which can annoy the operator and use up the limit so a real request is not sent. | Low | Global limit; only sent to `ADMIN_EMAIL`; identical response | Real requests can be crowded out during abuse |
| R11 | **Slow hashing used to exhaust the server.** Each attempt uses significant memory and CPU. | Medium | Concurrency cap on hashing; check the limit before hashing | Hashing queue could slow legitimate admin use during an attack |
| R12 | **Locked out with no recovery.** Email is broken or off and the operator cannot redeploy, or logs have rolled over. | Medium | Variable-based reset; expiry creates a new password at next startup | Requires access to the platform's environment and logs |
| R13 | **Upgrade surprises.** Enabling login silently removes the allowlist, and the new Origin check could block existing IP-allowlist setups behind a proxy that rewrites `Host`. | Medium | Clear startup log line; documentation | Needs testing behind Nginx Proxy Manager |
| R14 | **Email security scanners opening links.** Automated scanners may fetch reset links. | Low | Opening a link changes nothing; only the form submission uses the token | None known |
| R15 | **Reset variable left in place.** A stale `ADMIN_PASSWORD_RESET` must not reset the password on each restart or new instance. | Medium | Each distinct value applies once | The value is stored and compared, so it should not be reused |
| R16 | **Several instances starting together.** Each could create a different temporary password, so the logged one might not work. | Medium | Create under a database lock; only the creating instance logs it | Needs testing on PostgreSQL, which CI does not run yet (#43) |
| R17 | **No audit trail.** A misused panel leaves little evidence beyond access logs. | Low | Alert on password change | Out of scope for now |
| R18 | **Forged IPs remain elsewhere.** This change does not fix the per-IP email limits on hosted platforms. | Medium | Tracked in #12 | Still open after this change |

## Open questions

1. Should a configured `ADMIN_EMAIL` receive a setup link instead of logging a temporary password? *Proposed: yes*, as it removes R2 on those installs.
2. Basic Auth, or a login page with a session cookie? A login page adds logout and an obvious "Forgot password?" link, but also sessions and cookies. *Proposed: Basic Auth.*
3. Should login replace the allowlist, or optionally apply on top of it? *Proposed: replace.*
4. Should a successful login, or only a password change, trigger an alert email? *Proposed: password change only.*
5. Should failed-login limits move to the database to resolve R9? *Proposed: not for the first version.*
6. Should a password reset also be possible through the CLI for self-hosted operators? *Proposed: yes, later.*
7. Are the 24-hour, one-hour, 12-character and 20-failures-per-5-minutes values right? *Proposed: yes.*
