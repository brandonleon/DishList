## MODIFIED Requirements

### Requirement: Host dashboard shows event dishes
The system SHALL render, on `GET /manage/{token}`, the event's host-contributed dishes, guest-contributed dishes, and the full dietary tag library. The route SHALL read the `flash_success` and `flash_error` query parameters, pass them to the template context, and the dashboard SHALL display any supplied message as plain (escaped) text.

#### Scenario: Dishes split by contributor type
- **WHEN** `GET /manage/{token}` is requested for an event with both host and guest dishes
- **THEN** host-contributed dishes and guest-contributed dishes are provided to the template as separate lists

#### Scenario: Flash message rendered from query params
- **WHEN** `GET /manage/{token}?flash_error=Something+went+wrong` is requested
- **THEN** the dashboard shows "Something went wrong" as an error message, with any markup in the message escaped

### Requirement: Host can add and delete host-contributed dishes
The system SHALL let the host add dishes via `POST /manage/{token}/host-items` (name, a dish type from the event's configured types, optional notes) and delete them via `POST /manage/{token}/host-items/{dish_id}/delete`. The dish name SHALL be non-empty after leading and trailing whitespace is removed.

#### Scenario: Unknown dish type on host item rejected
- **WHEN** the host submits a host item whose dish type is not among the event's configured types
- **THEN** the system responds with HTTP 400

#### Scenario: Whitespace-only dish name rejected
- **WHEN** the host submits a host item whose name contains only whitespace
- **THEN** the system responds with HTTP 400 and does not create the dish

### Requirement: Host can edit and delete any dish on their event
The system SHALL let the host edit (`GET/POST /manage/{token}/dishes/{dish_id}`) or delete (`POST /manage/{token}/dishes/{dish_id}/delete`) any dish — host- or guest-contributed — belonging to their event, applying the same dish-type and dietary-tag validation used for guest submissions. The dashboard SHALL offer an Edit action on both host-contributed and guest-contributed dishes. For a host-contributed dish the edit form SHALL expose only name, dish type and notes; its contributor and dietary tags SHALL be preserved unchanged on save, even if a submission includes values for them. For a guest-contributed dish, the contributor and dish name SHALL each be non-empty after leading and trailing whitespace is removed.

#### Scenario: Dish belongs to a different event
- **WHEN** a host targets a `dish_id` that exists but belongs to a different event than the one identified by their token
- **THEN** the system responds with HTTP 404 rather than exposing or modifying the dish

#### Scenario: Host edits a house dish
- **WHEN** the host saves the edit form for a host-contributed dish with a new name, type and notes
- **THEN** those three fields are updated, the dish remains a host-contributed dish, and its contributor and tags are unchanged

#### Scenario: Submitted contributor ignored for house dish
- **WHEN** a submission for a host-contributed dish includes a `contributor` value different from the stored one
- **THEN** the stored contributor is kept

#### Scenario: Blank contributor on guest dish rejected without saving
- **WHEN** the host saves a guest-contributed dish with a whitespace-only or missing contributor
- **THEN** the system responds with HTTP 400 and the stored dish is unchanged, so the dashboard continues to load

#### Scenario: Blank dish name rejected
- **WHEN** the host saves any dish with a whitespace-only dish name
- **THEN** the system responds with HTTP 400 and the stored dish is unchanged
