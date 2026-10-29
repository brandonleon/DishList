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
  - Anyone, on request (`/find`): one email listing everything stored under the address they type. Events they host come with the guest link and the management link; dishes they submitted come with the link to that Event's public page, never a management link.
- **Privacy:**
  - Addresses are private and never rendered. The Host's address is never shown to Guests.
  - The Management Token is only ever sent to the Host's own address, and the resend action never takes a recipient from the request.
  - Stored addresses are deleted once the Event is over: it is closed, its date passed (plus one day), or, with no date, 30 days after creation.
- **Abuse limits:** an in-memory sliding window caps sends per client IP, per recipient address, per Event for Host notices, and per Event for link resends. Over-limit addresses are dropped rather than failing the request.
- **Lookup without enumeration:** the lookup form returns the same redirect and message ("If an event or dish is associated with this email, you will receive an email with details.") whether the address is known, unknown or rate-limited, and the database lookup runs after the response so timing does not differ either. An unknown address sends nothing, so typos are never mailed. Malformed input is rejected before any lookup, which reveals nothing about stored addresses. Lookups have their own, stricter limits (per IP and 2 per address per hour) separate from the creation limits.
- **Delivery:** sent as FastAPI background tasks after the response. Failures are logged and never affect the request. There is no queue or retry.

## Consequences

- Hosts who give an address can recover their link without the CLI. Hosts who don't still rely on the CLI (`dishlist admin events token <id>`).
- Guests have no edit link; changes always go through the Host.
- Rate-limit state resets on restart and is per process. Behind a reverse proxy the client IP is whatever the proxy forwards.
- Sending from Resend to arbitrary recipients requires a verified sending domain.
- The lookup can only find live Events and Submissions: addresses are deleted when an Event ends, so a Host who loses a link after the Event is over cannot recover it this way.
- Anyone can ask for a lookup for any address, but the email only ever goes to that address, and the per-address limit keeps it from being used to flood an inbox.
- Because addresses are deleted after the Event, features that need them later (reminders, "your dish was edited") would need this retention rule revisited.
