# Spec Delta

## Purpose

Protect mock-backed demo payments from duplicate requests and event deliveries
without creating a second source of financial state.

## ADDED Requirements

### Requirement: W4-01 Each mock payment attempt has an idempotency key
The system SHALL send a required `Idempotency-Key` with each mock payment attempt and reuse it only with the identical mock payload.

#### Scenario: New mock payment attempt is created
- **WHEN** the backend creates a mock payment
- **THEN** it sends a key bound to that wallet and the exact `walletId`, `recipient`, `amountCents`, `currency`, and `qrId` values

#### Scenario: A new payment is intentionally initiated
- **WHEN** the user starts a distinct payment after a prior final result
- **THEN** the backend creates a new key and retains the prior mock payment unchanged

### Requirement: W4-02 Repeating an identical request returns the mock payment
The system SHALL preserve the same key and payload on retry and display the mock's response for the existing payment.

#### Scenario: Same key and same mock payload are repeated
- **WHEN** the backend retries a request with the original key and identical payload
- **THEN** the mock returns the existing payment and the UI displays its current status without inventing another payment

### Requirement: W4-03 Reusing a key with different payload is rejected
The system SHALL surface the mock's idempotency conflict when a key is reused with different request data.

#### Scenario: Amount or recipient differs
- **WHEN** a request reuses a key with a different mock payload
- **THEN** the API conflict is shown and no replacement key is generated automatically

### Requirement: W4-04 Duplicate mock events remain auditable
The system SHALL use the mock's duplicate-event response and may keep a non-financial local demo trace without duplicating payment state.

#### Scenario: Duplicate payment request is detected
- **WHEN** the same key and payload are submitted again
- **THEN** the existing mock payment ID is retained and no second payment is presented

#### Scenario: Duplicate provider event is detected
- **WHEN** an already delivered mock event is submitted again
- **THEN** the API reports the duplicate delivery and the UI re-queries the existing payment rather than applying another movement

### Requirement: W4-05 Demo evidence distinguishes retries from payments
The system SHALL distinguish API payment records from local retry/event-delivery evidence in the demo report.

#### Scenario: Demo report includes a retry
- **WHEN** the report includes a repeated request or duplicate event
- **THEN** the mock payment is counted once and local request/delivery evidence is labeled separately
