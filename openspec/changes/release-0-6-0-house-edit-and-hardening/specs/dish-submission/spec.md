## MODIFIED Requirements

### Requirement: Guests can submit a dish to an active event
The system SHALL accept dish submissions via `POST /e/{slug}/add` requiring a contributor name (1-80 chars), a dish name (1-120 chars), a dish type that must be one of the event's configured dish types, optional notes, and zero or more dietary tag IDs. The contributor name and dish name SHALL be non-empty after leading and trailing whitespace is removed.

#### Scenario: Successful submission
- **WHEN** a guest submits a valid dish to an active event
- **THEN** the dish is stored against that event and the guest is redirected to the public event page

#### Scenario: Submission to an inactive event rejected
- **WHEN** a guest requests the add-dish form or submits it for an event whose `is_active` flag is false
- **THEN** the system responds with HTTP 403 and does not accept the submission

#### Scenario: Unknown dish type rejected
- **WHEN** the submitted `dish_type` is not among the event's configured dish types
- **THEN** the system responds with HTTP 400

#### Scenario: Unknown dietary tag rejected
- **WHEN** any submitted dietary tag ID does not correspond to an existing tag
- **THEN** the system responds with HTTP 400 and the dish is not created

#### Scenario: Whitespace-only contributor or dish name rejected
- **WHEN** a guest submits a contributor name or a dish name that contains only whitespace
- **THEN** the system responds with HTTP 400 and does not create the dish
