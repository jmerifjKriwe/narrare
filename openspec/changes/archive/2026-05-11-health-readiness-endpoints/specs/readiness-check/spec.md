## ADDED Requirements

### Requirement: Readiness Probe with DB Check

The system SHALL expose a readiness endpoint that verifies critical dependencies before declaring itself ready to serve traffic.

#### Scenario: All dependencies healthy

- **WHEN** a GET request is made to `/ready`
- **AND** the database connection is healthy
- **THEN** the response SHALL have status 200
- **AND** the body SHALL contain `{"status": "ready"}`

#### Scenario: Database unreachable

- **WHEN** a GET request is made to `/ready`
- **AND** the database connection fails
- **THEN** the response SHALL have status 503
- **AND** the body SHALL contain `{"status": "unhealthy", ...}` with error details
