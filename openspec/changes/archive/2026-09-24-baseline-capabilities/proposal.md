## Why

DishList has no OpenSpec specs yet — `openspec/specs/` is empty even though the app has shipped through v0.5.0 with a working feature set. Without a baseline, every future change proposal has nothing to diff against, and there's no single source of truth for what the app is already supposed to do. This change captures the existing, shipped behavior as baseline specs so future changes can be expressed as deltas against known requirements.

This is a documentation-only change: no application code changes. It only touches `openspec/`.

## What Changes

- Add baseline specs for the eight capabilities the app already implements (see below), each written as `ADDED Requirements` describing current, observed behavior — not aspirational behavior.
- No application code, tests, or templates are modified.

## Capabilities

### New Capabilities
- `event-management`: Hosts create a potluck event (name, description, date, host name, dish categories, slug), and the event gets a public slug URL and a private management-token URL. Hosts can later edit event settings or deactivate the event.
- `guest-dish-board`: The public event page (`/e/{slug}`) lists host and guest dishes in card or table view, with client-side-triggered HTMX partial refresh and a name/dish/type/notes search filter.
- `dish-submission`: Guests submit a dish to an active event via a form (contributor, dish name, dish type, notes, dietary tags); inactive events reject new submissions.
- `dietary-tags`: A shared library of dietary tags grouped by category (dietary preferences, allergen warnings, content & serving) with keyword-based auto-suggest, a hidden/visible flag, and CRUD + reset-to-defaults management.
- `host-management`: The token-gated `/manage/{token}` dashboard lets a host edit event settings, add/delete host-contributed dishes, and edit/delete any submitted dish.
- `web-admin`: A system-operator panel at `/pantry-admin`, disabled by default and gated by an IP/CIDR allowlist, for managing default dish types, admin network allowlist, dietary tags, metrics settings, and deleting events.
- `cli-management`: The `dishlist` CLI (serve + admin subcommands) starts the server and manages config, networks, dish types, tags, events, metrics, and live config reload via SIGUSR1 — without needing web admin enabled.
- `health-metrics`: An unauthenticated `/health` endpoint reports DB connectivity and app version; a separately IP-gated `/metrics` endpoint exposes Prometheus counters/gauges for HTTP traffic, events, and dishes.

### Modified Capabilities
None — `openspec/specs/` is currently empty, so every capability above is new from OpenSpec's perspective.

## Impact

- **Affected paths**: `openspec/specs/**` only (new files). No changes to `app/`, `tests/`, or `docs/`.
- **Downstream effect**: Establishes the requirement baseline that subsequent `openspec change` proposals will diff against (e.g. modifying `host-management` or adding a new capability).
