# ADR-0006: Server-side rendering with HTMX and vanilla JS — no SPA framework

**Status:** Accepted  
**Date:** 2026-05-18

## Context

DishList needs a frontend. Options considered:

1. **SPA framework (React, Vue, etc.)** — client-side rendering, requires a build step, Node.js toolchain, and a separate API layer.
2. **Server-side rendering + HTMX + vanilla JS** — Jinja2 templates rendered by FastAPI, HTMX for partial page updates, vanilla JS only where the browser needs to react to user input without a round-trip.

DishList is a self-hosted tool with a small, focused UI. The interactions are simple: submit a form, view a list, filter results. There is no complex client-side state that would justify a SPA framework.

## Decision

The frontend is built with:
- **Jinja2** templates rendered server-side by FastAPI
- **HTMX** for partial page updates (live search fetches `table/rows` and `cards/grid` partials without a full page reload)
- **Bootstrap 5** for layout and component styles
- **Vanilla JS** for interactions that cannot wait for a server round-trip (tag keyword auto-detection, tag picker search/filter)

No SPA framework, no build step, no Node.js dependency.

## Consequences

- The app deploys as a single Python process. No separate frontend build, no `npm install`, no bundler.
- No JavaScript framework churn — the frontend does not have a dependency tree that needs updating every six months.
- Adding new pages or interactions follows the same pattern: a Jinja2 template + a FastAPI route, with HTMX for any partial updates.
- Client-side interactions are intentionally minimal. If a feature requires significant client-side state, prefer a server round-trip (HTMX) over introducing a JS framework.
- Do not introduce a SPA framework or JS build toolchain without revisiting this decision — the operational simplicity of a single-process deployment is a first-class concern.
