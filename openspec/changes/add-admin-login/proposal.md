# Add web admin login

> **Status: draft.** Under discussion, not approved for implementation. Open decisions are listed in `design.md`.

## Why

The web admin panel is protected only by an IP allowlist (ADR-0002). On hosts where the operator does not control the proxy, such as FastAPI Cloud, the client IP cannot be trusted, so the allowlist is not a reliable barrier. Those hosts also give the operator no CLI, so setup and recovery have to work with only environment variables, logs and, optionally, email.

## What Changes

- Add an optional password login for the web admin panel, turned on with an environment variable.
- Show a one-time temporary password in the logs at first startup, and require a new password at first login.
- Recover a forgotten password by email when email is configured, or through an environment variable when it is not.
- **BREAKING (only when enabled):** the login replaces the IP allowlist, so the panel becomes reachable from the internet.
- Refuse cross-site form submissions to admin routes, in both login and IP allowlist modes.
- Hosts and guests are unaffected and remain accountless (ADR-0004).

## Capabilities

### New Capabilities

- `admin-login`: enabling, signing in to, and recovering access to the web admin panel using a password.

### Modified Capabilities

None. No specs exist yet for the current admin behaviour.

## Impact

- **Code:** admin route guards, a new credentials table on SQLite and PostgreSQL, new admin pages, one new transactional email.
- **Configuration:** new environment variables for enabling, resetting and the recovery address.
- **Docs:** README, user guide, `CONTEXT.md`, and a new ADR amending ADR-0002.
- **Out of scope:** `/metrics` authentication, multiple admins, per-admin audit history, and trusted proxy settings on hosted platforms.
