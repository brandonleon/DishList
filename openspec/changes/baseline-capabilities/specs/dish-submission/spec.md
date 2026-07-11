## ADDED Requirements

### Requirement: Guests can submit a dish to an active event
The system SHALL accept dish submissions via `POST /e/{slug}/add` requiring a contributor name (1-80 chars), a dish name (1-120 chars), a dish type that must be one of the event's configured dish types, optional notes, and zero or more dietary tag IDs.

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

### Requirement: Add-dish form surfaces dietary tag auto-suggest
The system SHALL provide the add-dish form with the event's configured dish types, the full set of tag groups, a keyword-to-tag-ID map (for tags that define keywords) for client-side auto-detection, and a count of tags currently marked hidden.

#### Scenario: Hidden tag count reflects the shared tag library
- **WHEN** the add-dish form is rendered
- **THEN** `hidden_tag_count` equals the number of tags across all categories with `is_hidden` set
