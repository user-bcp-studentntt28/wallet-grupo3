# Spec Delta

## Purpose

Define a test-only onboarding journey backed by the group-3 mock KYC and wallet
API, while distinguishing this demo from the broader W1 product requirements.

## ADDED Requirements

### Requirement: W1-01 The demo presents a guided responsive onboarding flow
The system SHALL show the current onboarding step and the next action in a responsive demo experience.

#### Scenario: User opens onboarding on a supported viewport
- **WHEN** a user opens the registration flow at 360 px or 1280 px
- **THEN** required fields and actions remain visible and the current step and next action are clear

### Requirement: W1-02 Onboarding submits only mock test identity values
The system SHALL submit only `documentType: TEST` and a fictitious `document` value beginning with `TEST-`.

#### Scenario: Document value is missing or not test-prefixed
- **WHEN** a user submits an empty value or one without the `TEST-` prefix
- **THEN** the UI explains the correction and sends no KYC request

#### Scenario: Valid test identity is submitted
- **WHEN** a user submits a non-empty `TEST-` value
- **THEN** the backend sends only the documented mock KYC fields and no real identity data

### Requirement: W1-03 Onboarding reflects the mock KYC result
The system SHALL display the KYC and wallet result returned by the group-3 mock without inventing an account state.

#### Scenario: Mock approves the KYC
- **WHEN** `POST /kyc/verifications` returns an `APPROVED` result
- **THEN** the UI shows the returned KYC and wallet IDs and obtains the wallet state from the mock

#### Scenario: Mock rejects or cannot process the KYC
- **WHEN** the mock returns `REJECTED` or `503 KYC_UNAVAILABLE`
- **THEN** the UI shows the returned rejection or unavailable result and does not claim that an active wallet was created

### Requirement: W1-04 Manual review requires an explicit human decision
The system SHALL keep a `MANUAL_REVIEW` KYC pending until a human facilitator chooses a final decision.

#### Scenario: Mock places a KYC in manual review
- **WHEN** the mock returns `MANUAL_REVIEW`
- **THEN** the UI shows `PENDING` and does not activate the wallet automatically

#### Scenario: Facilitator resolves a pending KYC
- **WHEN** a human facilitator explicitly chooses `ACTIVE` or `REJECTED`
- **THEN** the backend sends that decision to the documented mock endpoint and displays the returned result

### Requirement: W1-05 Wallet status and balance come from the mock
The system SHALL query and display wallet status and balances from the mock in integer PEN cents, without creating a local wallet balance.

#### Scenario: Newly created wallet is queried
- **WHEN** a newly created test wallet is retrieved
- **THEN** the UI displays the returned status and zero balance rather than implying that onboarding funded it

#### Scenario: Seeded demo wallet is used
- **WHEN** the payment walkthrough selects `wallet-demo`
- **THEN** the UI displays the current balance returned by the mock and labels it as shared group test data

### Requirement: W1-06 Onboarding evidence contains no personal data
The system SHALL record demo onboarding events with a local session reference, returned wallet ID when available, and local timestamps without storing the submitted document value.

#### Scenario: Onboarding trace is exported
- **WHEN** a user exports the demo trace
- **THEN** it contains the recorded steps and timestamps but no document value, credentials, or claim of provider-originated timestamps

### Requirement: W1-07 Mock KYC is not represented as production identity verification
The system SHALL label KYC as simulated and SHALL NOT claim a RENIEC, SUNAT, Google, biometric, or real identity check.

#### Scenario: User views a KYC result
- **WHEN** the UI displays an onboarding decision
- **THEN** it identifies the result as a group-3 mock outcome and does not present it as verified real-world identity
