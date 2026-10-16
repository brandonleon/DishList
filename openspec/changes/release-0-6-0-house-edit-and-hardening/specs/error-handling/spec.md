## Purpose

Defines how request errors are presented so people using a browser see a readable page with a way back, while scripts and tests keep receiving machine-readable errors with unchanged HTTP status codes.

## ADDED Requirements

### Requirement: Browsers receive an HTML error page
For any HTTP error response raised by the application, when the request's `Accept` header prefers `text/html`, the system SHALL respond with an HTML page that shows the status code, a human-readable message and a link back to the home page, and SHALL keep the original HTTP status code.

#### Scenario: Browser submits an invalid form
- **WHEN** a browser (sending `Accept: text/html`) submits a form that the server rejects with HTTP 400 and a detail message
- **THEN** the response has status 400 and an HTML body that shows that message

#### Scenario: Browser submits a value that fails field validation
- **WHEN** a browser submits a form whose field values fail request validation (HTTP 422)
- **THEN** the response has status 422 and an HTML body that names the offending field(s)

#### Scenario: Message text is escaped
- **WHEN** an error detail contains HTML markup
- **THEN** the markup is displayed as text and not interpreted

### Requirement: Other clients keep JSON errors
When the request does not prefer `text/html` (for example `Accept: */*` or `application/json`), the system SHALL respond with the same JSON error body as before this requirement existed.

#### Scenario: Non-browser client gets JSON
- **WHEN** a client sending `Accept: application/json` triggers an HTTP 404
- **THEN** the response has status 404 and a JSON body containing a `detail` field

#### Scenario: Validation errors stay JSON for other clients
- **WHEN** a client not preferring `text/html` submits a request that fails field validation (HTTP 422)
- **THEN** the response has status 422 and the standard JSON body whose `detail` lists the errors
