## ADDED Requirements

### Requirement: Login is opt-in
The system SHALL leave web admin behaviour unchanged unless `ADMIN_LOGIN_ENABLED` is set to a true value. When it is enabled, the password login SHALL replace the IP allowlist for the web admin panel.

#### Scenario: Login not enabled
- **WHEN** `ADMIN_LOGIN_ENABLED` is unset
- **THEN** no temporary password is created and the existing IP allowlist behaviour applies

#### Scenario: Login enabled
- **WHEN** `ADMIN_LOGIN_ENABLED` is true and a request has no valid login
- **THEN** the panel responds 401, whatever client IP the request presents

### Requirement: Temporary password at first startup
The system SHALL create one random temporary password when login is enabled and no admin password exists, store only its hash, and write it to the logs once. It SHALL expire 24 hours after creation.

#### Scenario: Several instances start together
- **WHEN** multiple instances start with no admin password stored
- **THEN** exactly one temporary password is created and only the creating instance logs it

#### Scenario: Restart before first login
- **WHEN** the app restarts while an unexpired temporary password is pending
- **THEN** the password is unchanged and is not logged again

#### Scenario: Temporary password expires
- **WHEN** the app starts after a pending temporary password has expired
- **THEN** the expired password stops working and a new one is created and logged

### Requirement: Password change at first login
The system SHALL refuse all admin actions made with a temporary password, other than setting a new password. A new password SHALL have at least 12 characters, match its confirmation, and differ from the current password.

#### Scenario: Admin page with a temporary password
- **WHEN** an operator logged in with a temporary password opens an admin page
- **THEN** they are redirected to the page for setting a new password

#### Scenario: Admin action with a temporary password
- **WHEN** a temporary password is used to submit any other admin form
- **THEN** the action is not performed

#### Scenario: Password set
- **WHEN** a valid new password is submitted
- **THEN** the temporary password stops working and the new password grants access

#### Scenario: Password refused
- **WHEN** a new password is too short, does not match its confirmation, or equals the current password
- **THEN** the password is unchanged and the operator sees the reason

### Requirement: Credentials are protected
The system SHALL store admin passwords and recovery tokens only as hashes, and SHALL NOT write a permanent password or recovery token to the logs.

#### Scenario: Database contents
- **WHEN** the stored admin credentials are read directly
- **THEN** no password or recovery token can be read from them in plain text

### Requirement: Failed logins are limited
The system SHALL limit failed admin logins globally rather than per client IP, and SHALL respond 429 while the limit applies, even to a correct password.

#### Scenario: Limit reached
- **WHEN** 20 failed logins occur within 5 minutes
- **THEN** further login attempts receive 429 until the window passes

#### Scenario: Forged client IPs
- **WHEN** failed logins present a different forwarded IP on each request
- **THEN** they all count toward the same limit

### Requirement: Cross-site admin submissions are refused
The system SHALL refuse admin POST requests whose `Origin` header does not match the request host, in both login and IP allowlist modes, including password and recovery forms.

#### Scenario: Submission from another site
- **WHEN** an admin POST has an `Origin` from another site, or `null`
- **THEN** the system responds 403 and performs no action

#### Scenario: Same-site submission
- **WHEN** an admin POST has an `Origin` matching the request host and is otherwise authorized
- **THEN** the action is performed

### Requirement: Email recovery
The system SHALL offer password recovery by email only when login is enabled, email is configured, and `ADMIN_EMAIL` and `PUBLIC_BASE_URL` are set. Recovery links SHALL be built only from `PUBLIC_BASE_URL`, be sent only to `ADMIN_EMAIL`, work once, and expire after one hour.

#### Scenario: Recovery not configured
- **WHEN** any of the required settings is missing
- **THEN** the recovery pages respond 404

#### Scenario: Forged Host header
- **WHEN** recovery is requested with a forged `Host` header
- **THEN** the emailed link still uses `PUBLIC_BASE_URL`

#### Scenario: Recovery requested
- **WHEN** recovery is requested
- **THEN** the current password keeps working until a new one is set using the link

#### Scenario: Link opened
- **WHEN** a recovery link is opened without submitting the form
- **THEN** the link remains usable and the password is unchanged

#### Scenario: Link used
- **WHEN** a valid new password is submitted through a recovery link
- **THEN** the old password and the link both stop working

#### Scenario: Requests exceed the limit
- **WHEN** recovery requests exceed the limit of 3 per hour
- **THEN** no further email is sent and the response looks the same as a successful request

### Requirement: Recovery without email
The system SHALL let an operator replace the admin password by setting `ADMIN_PASSWORD_RESET` to a new value. Each distinct value SHALL take effect once.

#### Scenario: New reset value
- **WHEN** the app starts with an `ADMIN_PASSWORD_RESET` value it has not used
- **THEN** a new temporary password replaces the current password and is logged once

#### Scenario: Value left in place
- **WHEN** the app restarts, or a new instance starts, with an already used value
- **THEN** the password is unchanged

### Requirement: Hosts and guests stay accountless
The system SHALL NOT require a login for guest boards, dish submission, or management links.

#### Scenario: Public routes with login enabled
- **WHEN** login is enabled
- **THEN** guest and management-link routes behave as they did before
