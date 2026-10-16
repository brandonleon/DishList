# dietary-tags Specification

## Purpose
Provides a shared library of dietary and allergen tags that guests attach to dishes, with keyword auto-suggest and administrator controls.
## Requirements
### Requirement: Dietary tags are grouped by category with a defined order
The system SHALL organize dietary tags into categories (e.g. "Dietary preferences", "Allergen warnings", "Content & serving") and SHALL preserve a per-tag `position` for display ordering within a category. Tags SHALL be shared across all events rather than scoped per event.

#### Scenario: New category created on demand
- **WHEN** a tag is created with a category name that does not yet exist
- **THEN** the system accepts the new category rather than rejecting the tag

### Requirement: Tags carry keywords for auto-suggest
The system SHALL allow each tag to define a list of keywords used by the client to auto-detect likely dietary tags from free-text dish names or notes.

#### Scenario: Tag without keywords is omitted from the keyword map
- **WHEN** a tag has no keywords defined
- **THEN** it is excluded from the keyword-to-tag-ID map built for client-side auto-detection

### Requirement: Tags can be hidden without losing existing associations
The system SHALL support an `is_hidden` flag per tag. Hidden tags SHALL be excluded from default suggestion counts shown to submitters but SHALL remain valid tag IDs that existing dishes keep referencing.

#### Scenario: Toggling visibility
- **WHEN** an admin toggles a tag's visibility
- **THEN** the tag's `is_hidden` flag flips and dishes already tagged with it are unaffected

### Requirement: Tag library supports admin CRUD and reset to defaults
The system SHALL let an administrator create, update, and delete tags, and SHALL support resetting the entire tag library back to a built-in default set. A reset SHALL clear dietary-tag associations from every dish.

#### Scenario: Duplicate tag rejected
- **WHEN** an admin tries to create or rename a tag to a name that already exists anywhere in the tag library (compared case-insensitively, regardless of category)
- **THEN** the system rejects the change with a validation error and leaves the tag library unchanged

#### Scenario: Reset replaces all tags and clears associations
- **WHEN** the tag library is reset to defaults (via CLI or web admin)
- **THEN** all tags are replaced with the defaults and every dish's tag associations are cleared

#### Scenario: Reset is confirmed before it runs
- **WHEN** an operator starts a reset from the CLI or from the web admin form
- **THEN** the CLI asks for interactive confirmation and the web admin form asks for browser-side confirmation before the reset is submitted

