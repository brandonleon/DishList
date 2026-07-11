## Context

DishList already exists and works; this change writes down its current behavior as OpenSpec specs. There is no code to design — the specs in this change describe observed behavior read directly from `app/main.py`, `app/cli.py`, `app/storage.py`, `app/config.py`, and `app/metrics.py`.

## Goals / Non-Goals

**Goals:**
- Produce accurate baseline specs for the eight capabilities listed in the proposal.

**Non-Goals:**
- No architecture, data model, or behavior changes.
- No new dependencies, migrations, or deployment steps.

## Decisions

- Split by user-facing capability (event-management, guest-dish-board, dish-submission, dietary-tags, host-management, web-admin, cli-management, health-metrics) rather than by code module, since OpenSpec capabilities are meant to map to behavior a reader would want to diff against, not to `app/` file boundaries.
- Documented only currently-implemented behavior (drawn from route handlers and CLI commands), omitting anything speculative.

## Risks / Trade-offs

- [Risk] Specs could drift from code already at the moment of writing if a detail was missed during review. → Mitigation: this change is reviewed against `app/main.py` and `app/cli.py` before archiving, and any future behavior change should update the relevant spec in the same PR.
