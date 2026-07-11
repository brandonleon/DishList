## ADDED Requirements

### Requirement: Public event page lists host and guest dishes
The system SHALL serve a public page at `GET /e/{slug}` that separates dishes into host-contributed items and guest-contributed items, loaded from storage for that event only.

#### Scenario: Unknown event slug
- **WHEN** a request is made to `/e/{slug}` for a slug with no matching event
- **THEN** the system responds with HTTP 404

### Requirement: Board supports card and table view modes
The system SHALL support a `view` query parameter of `cards` or `table` on the event page, defaulting to `cards` when the parameter is absent or holds any other value.

#### Scenario: Invalid view mode falls back to cards
- **WHEN** `GET /e/{slug}?view=unexpected` is requested
- **THEN** the page renders in card view rather than erroring

### Requirement: Guest dishes are searchable
The system SHALL filter guest-contributed dishes by a case-insensitive substring match against dish name, contributor, dish type, or notes when a `search` query parameter is supplied. Host-contributed dishes SHALL always be shown unfiltered and separately from the searchable guest list.

#### Scenario: Search matches across fields
- **WHEN** the search term matches a dish's notes but not its name or contributor
- **THEN** that dish still appears in the filtered results

### Requirement: Board refreshes via HTMX partials without a full reload
The system SHALL expose `GET /e/{slug}/table/rows` and `GET /e/{slug}/cards/grid` as partial-HTML endpoints, both accepting the same `search` parameter as the main page, so the client can refresh only the dish listing.

#### Scenario: Partial reflects the same filter as the full page
- **WHEN** `GET /e/{slug}/table/rows?search=<term>` is requested
- **THEN** it returns the same filtered guest-dish rows that `GET /e/{slug}?view=table&search=<term>` would render
