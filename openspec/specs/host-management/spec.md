# host-management Specification

## Purpose
Gives the host a private, token-gated dashboard to manage the event's dishes: add, edit and remove house dishes and edit or delete any guest dish.
## Requirements
### Requirement: Management token is the sole credential for the host dashboard
The system SHALL grant access to `/manage/{token}` based solely on possession of the event's management token — no separate login or password is required. An unknown token SHALL be treated as not found.

#### Scenario: Unknown management token
- **WHEN** a request is made to `/manage/{token}` with a token that matches no event
- **THEN** the system responds with HTTP 404

### Requirement: Host dashboard shows event dishes
The system SHALL render, on `GET /manage/{token}`, the event's host-contributed dishes, guest-contributed dishes, and the full dietary tag library. The route SHALL read the `flash_success` and `flash_error` query parameters and pass them to the template context.

#### Scenario: Dishes split by contributor type
- **WHEN** `GET /manage/{token}` is requested for an event with both host and guest dishes
- **THEN** host-contributed dishes and guest-contributed dishes are provided to the template as separate lists

### Requirement: Host can add and delete host-contributed dishes
The system SHALL let the host add dishes via `POST /manage/{token}/host-items` (name, a dish type from the event's configured types, optional notes) and delete them via `POST /manage/{token}/host-items/{dish_id}/delete`.

#### Scenario: Unknown dish type on host item rejected
- **WHEN** the host submits a host item whose dish type is not among the event's configured types
- **THEN** the system responds with HTTP 400

### Requirement: Host can edit and delete any dish on their event
The system SHALL let the host edit (`GET/POST /manage/{token}/dishes/{dish_id}`) or delete (`POST /manage/{token}/dishes/{dish_id}/delete`) any dish — host- or guest-contributed — belonging to their event, applying the same dish-type and dietary-tag validation used for guest submissions.

#### Scenario: Dish belongs to a different event
- **WHEN** a host targets a `dish_id` that exists but belongs to a different event than the one identified by their token
- **THEN** the system responds with HTTP 404 rather than exposing or modifying the dish

