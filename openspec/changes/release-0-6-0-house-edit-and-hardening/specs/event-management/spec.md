## MODIFIED Requirements

### Requirement: Host can create a potluck event
The system SHALL allow anyone to create a new event via `GET/POST /create` by supplying a name (1-120 chars after leading and trailing whitespace is removed, required), an optional description, an optional ISO event date, an optional host name (at most 80 chars; defaults to "The House" when blank), and a newline-separated list of dish categories (at least one required).

#### Scenario: Successful event creation
- **WHEN** a visitor submits the create-event form with a name and at least one dish type
- **THEN** the system creates the event and redirects to its management dashboard at `/manage/{management_token}`

#### Scenario: Missing dish types rejected
- **WHEN** the submitted `dish_types_input` contains no non-blank lines
- **THEN** the system responds with HTTP 400 and does not create the event

#### Scenario: Invalid event date rejected
- **WHEN** the submitted `event_date` is not a valid ISO date string
- **THEN** the system responds with HTTP 400 and does not create the event

#### Scenario: Whitespace-only event name rejected
- **WHEN** the submitted `name` contains only whitespace
- **THEN** the system responds with HTTP 400 and does not create the event

#### Scenario: Over-long host name rejected
- **WHEN** the submitted host name is longer than 80 characters
- **THEN** the system responds with HTTP 422 and does not create the event

### Requirement: Host can edit event settings after creation
The system SHALL let the host update the event's name, description, date, host name, dish categories, and active status via `POST /manage/{token}`, applying the same validation as event creation. When the host name changes, the system SHALL update the contributor of the event's existing host-contributed dishes to the new host name; guest-contributed dishes SHALL NOT be affected.

#### Scenario: Host deactivates the event
- **WHEN** the host submits the management form with `is_active` unchecked
- **THEN** the event is marked inactive and guest dish submissions to it are subsequently rejected

#### Scenario: Whitespace-only event name rejected
- **WHEN** the host submits the management form with a name containing only whitespace
- **THEN** the system responds with HTTP 400 and the event's stored settings are unchanged

#### Scenario: Over-long host name rejected
- **WHEN** the host submits the management form with a host name longer than 80 characters
- **THEN** the system responds with HTTP 422 and the event's stored settings are unchanged

#### Scenario: Renaming the host updates house dishes
- **WHEN** the host changes the host name from "The House" to "The Smokehouse" on an event that has host-contributed and guest-contributed dishes
- **THEN** every host-contributed dish shows "The Smokehouse" as its contributor and guest-contributed dishes keep their contributors
