# Spec Delta

## Purpose

Present mock payment errors and statuses accurately, and provide read-only
support guidance without claiming debt validation or invoking reversals.

## ADDED Requirements

### Requirement: W5-01 Mock errors and final statuses are shown accurately
The system SHALL preserve the mock's error code and payment status in demo evidence and SHALL NOT invent a payment `EXPIRED` status.

#### Scenario: Mock rejects a payment
- **WHEN** the mock reports `REJECTED`
- **THEN** the UI reports rejection and preserves the returned payment ID/status

#### Scenario: Mock reports provider or QR error
- **WHEN** the mock returns `503`, `504`, or QR expiry `410`
- **THEN** the UI preserves the actual error and does not relabel it as a final rejected or expired payment unless the API says so

### Requirement: W5-02 Support guidance distinguishes retry from investigation
The system SHALL direct users to retry only when the mock confirms that no payment was created and to query/resolve when the outcome is uncertain.

#### Scenario: Provider error created no payment
- **WHEN** the mock returns `503 PROVIDER_ERROR` and confirms no operation or reservation
- **THEN** the UI offers a controlled new attempt with a new idempotency key

#### Scenario: Outcome is uncertain or inconsistent
- **WHEN** the mock returns `504` after processing or its status cannot be queried
- **THEN** the UI retains the payment ID when provided, offers query/resolve, and does not create another payment automatically

### Requirement: W5-03 User guidance distinguishes mock payment states
The system SHALL map `PENDING`, `SUCCEEDED`, and `REJECTED` to clear Spanish labels and SHALL not present a pending or uncertain outcome as successful.

#### Scenario: User requests help for a rejected or uncertain payment
- **WHEN** a payment is `REJECTED`, `PENDING`, or has an uncertain timeout
- **THEN** the user sees the raw mock state, a safe next action, and no fabricated balance movement

#### Scenario: User requests reversal of a successful payment
- **WHEN** a payment is `SUCCEEDED`
- **THEN** the demo offers no reversal, refund, or dispute action, in accordance with W5

### Requirement: W5-04 Support access is read-only and evidence-based
Support and operations SHALL NOT sign in as wallet owners or mutate payment data through the demo; support information SHALL be limited to what the mock API returns.

#### Scenario: Support case is queried
- **WHEN** an operator views the mock's support cases for a payment
- **THEN** the UI displays returned case details and labels any local capture timestamp as demo evidence

#### Scenario: Support role attempts a wallet operation
- **WHEN** a support or operations view attempts to create a payment or call the reversal endpoint
- **THEN** the demo denies the action

### Requirement: W5-05 Reversals and disputes remain outside the demo
The system SHALL NOT call the mock reversal endpoint or implement refunds, chargebacks, or dispute resolution in this demo.

#### Scenario: Shared mock already reports a reversed payment
- **WHEN** a queried mock record is already `REVERSED`
- **THEN** the UI displays that returned status without initiating or hiding a reversal
