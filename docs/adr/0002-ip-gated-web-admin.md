# ADR-0002: IP-gated Web Admin Panel instead of password authentication

**Status:** Accepted  
**Date:** 2026-05-18

## Context

DishList needs a System Admin interface for managing Tags, Events, Dish Types, and network settings. Two access control approaches were considered:

1. **Password authentication** — a username/password login protecting the admin panel.
2. **IP allowlist gating** — the panel is only reachable from explicitly allowed IPs or CIDR ranges; disabled entirely by default.

DishList is a self-hosted tool where the System Admin controls the network. It has no user account system — adding one only for the admin panel would introduce significant complexity (session management, credential storage, password reset flows).

## Decision

The Web Admin Panel is protected by an IP allowlist rather than a password. The panel is disabled by default and returns 404 when disabled, revealing nothing about its existence. When enabled, it is only reachable from IPs within the configured allowlist.

The CLI (`dishlist admin`) is always available as the primary admin interface, independent of the Web Admin Panel's state.

## Consequences

- No credential storage, session management, or password reset complexity.
- An attacker on the public internet cannot reach the panel at all — it does not exist to them.
- The System Admin must manage their own network access (VPN, local network, etc.) to use the web panel.
- The IP allowlist must be configured before enabling the panel — the CLI enforces this.
- This model is inappropriate for multi-tenant or cloud-hosted deployments where the admin does not control the network. If DishList is ever offered as a hosted service, this decision should be revisited.
