# ADR-0007: Optional email via Resend, no accounts

**Status:** Accepted  
**Date:** 2026-10-29

## Context

[ADR-0004](./0004-no-user-accounts.md) removed accounts, which means a Host who loses their Management Token has no self-service recovery. Guests also get no confirmation of what they signed up to bring. Email would fix both, but it must not reintroduce accounts, make email mandatory, or turn a public form into a way to spam strangers.

## Decision

Email is an optional, operator-enabled feature.

- **Provider:** Resend's HTTP API, called with `httpx`. Enabled only when `RESEND_API_KEY` and `RESEND_FROM` are set; `PUBLIC_BASE_URL` sets the origin used in links. When unset, email fields are hidden and no address is accepted or stored.
- **What is sent:**
  - Host, on Event creation: the Management link, Guest Board link and a summary. The Host can re-send it from the Management Page.
  - Host, optionally (checkbox at creation): a notice for each new Submission.
  - Guest, optionally (field on the add form): a confirmation that tells them to ask the Host for any change.
- **Privacy:**
  - Addresses are private and never rendered. The Host's address is never shown to Guests.
  - The Management Token is only ever sent to the Host's own address, and the resend action never takes a recipient from the request.
  - Stored addresses are deleted once the Event is over: it is closed, its date passed (plus one day), or, with no date, 30 days after creation.
- **Abuse limits:** an in-memory sliding window caps sends per client IP, per recipient address, per Event for Host notices, and per Event for link resends. Over-limit addresses are dropped rather than failing the request.
- **Delivery:** sent as FastAPI background tasks after the response. Failures are logged and never affect the request. There is no queue or retry.

## Consequences

- Hosts who give an address can recover their link without the CLI. Hosts who don't still rely on the CLI (`dishlist admin events token <id>`).
- Guests have no edit link; changes always go through the Host.
- Rate-limit state resets on restart and is per process. Behind a reverse proxy the client IP is whatever the proxy forwards.
- Sending from Resend to arbitrary recipients requires a verified sending domain.
- Because addresses are deleted after the Event, features that need them later (reminders, "your dish was edited") would need this retention rule revisited.
