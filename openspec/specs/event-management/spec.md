# event-management Specification

## Purpose
Lets a host create a potluck event and later change its settings, giving it a public link for guests and a private management link for the host.
## Requirements
### Requirement: Host can create a potluck event
The system SHALL allow anyone to create a new event via `GET/POST /create` by supplying a name (1-120 chars, required), an optional description, an optional ISO event date, an optional host name (defaults to "The House" when blank), and a newline-separated list of dish categories (at least one required).

#### Scenario: Successful event creation
- **WHEN** a visitor submits the create-event form with a name and at least one dish type
- **THEN** the system creates the event and redirects to its management dashboard at `/manage/{management_token}`

#### Scenario: Missing dish types rejected
- **WHEN** the submitted `dish_types_input` contains no non-blank lines
- **THEN** the system responds with HTTP 400 and does not create the event

#### Scenario: Invalid event date rejected
- **WHEN** the submitted `event_date` is not a valid ISO date string
- **THEN** the system responds with HTTP 400 and does not create the event

### Requirement: Every event has a public slug and a private management token
The system SHALL generate a unique public slug and a separate, unguessable management token for each event at creation time. The slug SHALL identify the public event page (`/e/{slug}`); the management token SHALL identify the host dashboard (`/manage/{token}`) and SHALL NOT be derivable from the slug.

#### Scenario: Slug derived from event name
- **WHEN** an event is created without requesting a random slug
- **THEN** the system slugifies the event name and appends a numeric suffix if that slug is already taken, guaranteeing uniqueness

#### Scenario: Random slug requested
- **WHEN** the create form's `use_random_slug` field is set
- **THEN** the system generates a random slug instead of deriving one from the event name

#### Scenario: Unknown slug or token
- **WHEN** a request references a slug or management token that does not match any event
- **THEN** the system responds with HTTP 404

### Requirement: Host contributions can be added at event creation time
The system SHALL accept parallel lists of host item names, types, and notes on the create-event form and SHALL add each non-blank item as a host-attributed dish (`is_host_item=True`, contributor set to the event's host name) belonging to the new event.

#### Scenario: Host item with unlisted type falls back
- **WHEN** a host item's submitted dish type is not among the event's configured dish types
- **THEN** the system assigns the item the event's first configured dish type instead of rejecting it

### Requirement: Host can edit event settings after creation
The system SHALL let the host update the event's name, description, date, host name, dish categories, and active status via `POST /manage/{token}`, applying the same validation as event creation.

#### Scenario: Host deactivates the event
- **WHEN** the host submits the management form with `is_active` unchecked
- **THEN** the event is marked inactive and guest dish submissions to it are subsequently rejected

