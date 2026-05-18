# ADR-0004: No user accounts — token-based Host identity

**Status:** Accepted  
**Date:** 2026-05-18

## Context

DishList needs a way to distinguish Hosts (who manage Events) from Guests (who submit Dishes). Options considered:

1. **User accounts** — email/password registration, sessions, password reset flows.
2. **Token-based identity** — a Management Token issued at Event creation serves as the Host's sole credential. No registration, no sessions.

The app's core value proposition is zero-friction participation: a Guest should be able to submit a Dish in under a minute with no signup. Introducing accounts even just for Hosts would add session management, credential storage, and password reset complexity that the app does not need.

## Decision

There are no user accounts in DishList. Host identity is represented entirely by the Management Token — an unguessable 32-byte URL-safe secret issued once at Event creation. Guests have no persistent identity; their name on a Submission is a self-reported display name.

## Consequences

- Zero friction for Guests: no signup, no login, no email required.
- Zero session management complexity: no cookies, no auth middleware, no credential storage.
- The Management Token is the Host's only credential. If it is lost, the Host cannot access the Management Page without System Admin intervention via the CLI (`dishlist admin events list` to find the token, or direct database inspection).
- There is no "forgot my management link" self-service flow. This is a known limitation — if a self-service recovery path becomes necessary, it should be implemented as a future feature rather than by retrofitting accounts.
- This model assumes a single Host per Event. If co-hosting (multiple people sharing management access) becomes a requirement, this decision should be revisited.
