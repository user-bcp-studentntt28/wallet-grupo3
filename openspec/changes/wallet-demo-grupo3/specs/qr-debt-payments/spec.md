# Spec Delta

## Purpose

Define el recorrido de demo con QR y pago del mock del grupo 3. El criterio de
demo usa el `qrId` del proveedor; no afirma que ese QR sea un documento de deuda
W3 ni que el mock reciba un `documento_deuda_id`.

## ADDED Requirements

### Requirement: W2-01 Payment confirmation shows mock QR details
The system SHALL show the payer the merchant, QR amount, and PEN currency returned by the mock before payment confirmation.

#### Scenario: Payer reviews a valid fixed-amount QR
- **WHEN** the payer resolves a mock QR with a fixed amount
- **THEN** the merchant and amount from the mock are shown and the payer cannot change that amount

#### Scenario: Payer reviews an open-amount QR
- **WHEN** the payer resolves a mock QR with no fixed amount
- **THEN** the UI requests a positive PEN amount and explains it is a mock payment, not a W3 debt balance

### Requirement: W2-02 Payment uses an active mock wallet
The system SHALL submit a payment only with an active wallet ID returned by the mock and SHALL display the mock's available balance.

#### Scenario: Mock wallet is inactive or unavailable
- **WHEN** the selected mock wallet is not active or cannot be queried
- **THEN** the backend does not submit the payment and the UI reports the actual API error

### Requirement: W2-03 Payment request conforms to the mock
The system SHALL send only the documented mock payment fields, enforce PEN cents and accepted recipients, and let the mock validate wallet state, funds, QR merchant, amount, and expiry.

#### Scenario: Payment request is constructed
- **WHEN** the payer confirms a supported mock QR payment
- **THEN** the backend sends `walletId`, `recipient`, `amountCents`, `currency`, optional `qrId`, the required `Idempotency-Key`, and a test `scenario` only when selected through a separated test control

#### Scenario: Mock rejects payment data
- **WHEN** the mock returns an input, QR, wallet, or balance error
- **THEN** the UI displays the returned error safely and does not show a successful payment

### Requirement: W2-04 Payer confirms before payment creation
The system SHALL require an explicit user confirmation before the backend calls the mock's payment-creation endpoint.

#### Scenario: Payer confirms a resolved QR
- **WHEN** the payer confirms the QR details and amount
- **THEN** the backend creates one mock payment using the confirmed amount and QR identifier

#### Scenario: Payer cancels confirmation
- **WHEN** the payer cancels before confirmation
- **THEN** no payment-creation request is sent to the mock

### Requirement: W2-05 Mock owns payment reservation
The system SHALL treat the mock's payment response and wallet query as authoritative for payment state and reserved/available funds; the demo SHALL NOT create a local financial reservation.

#### Scenario: Mock accepts a payment request
- **WHEN** the mock accepts a payment request
- **THEN** the UI displays its returned payment ID and current status without inventing a local debt transition

#### Scenario: Mock reports a pending reservation
- **WHEN** the payment response is `202 PENDING`
- **THEN** the UI reports pending and shows the mock's available/reserved balance rather than mutating an application balance

### Requirement: W2-06 Asynchronous mock outcome remains pending
The system SHALL keep a mock payment pending until the API reports its final state through the documented query, event-delivery, or resolve flow.

#### Scenario: Mock returns pending or no final outcome
- **WHEN** the mock returns `PENDING` or no final outcome is available
- **THEN** the UI stays pending and does not report success

#### Scenario: Mock returns a final outcome
- **WHEN** the mock reports `SUCCEEDED` or `REJECTED` for the returned payment ID
- **THEN** the UI displays that mock status and refreshes the mock wallet and history

### Requirement: W2-07 Mock owns final status and balance movement
The system SHALL display the mock's persisted final payment and wallet state without creating or updating a second financial ledger.

#### Scenario: Mock payment succeeds
- **WHEN** the mock reports `SUCCEEDED`
- **THEN** the UI shows success only after re-querying the payment and wallet from the mock

#### Scenario: Mock payment is rejected
- **WHEN** the mock reports `REJECTED`
- **THEN** the UI shows rejection and the wallet state returned by the mock, without locally reversing or applying balances

#### Scenario: Mock query fails
- **WHEN** a payment or wallet re-query fails
- **THEN** the UI reports an unknown/unverified result and never substitutes a local success or balance

### Requirement: W2-08 Payment views use mock records
The system SHALL show payment history and receipts from the mock API and identify them as group-3 test data.

#### Scenario: Successful payment receipt is requested
- **WHEN** the payer requests the receipt for a mock `SUCCEEDED` payment
- **THEN** the UI displays only fields returned by the mock and does not invent a debt document or provider timestamp

#### Scenario: Wallet payment history is requested
- **WHEN** the user requests history for a mock wallet
- **THEN** the UI displays the API's wallet-scoped records and labels local capture timestamps separately from provider data

#### Scenario: Local demo reference is displayed
- **WHEN** a mock `qrId` and `paymentId` are associated with a local demo label
- **THEN** the UI labels that association as demo metadata, not as a provider-verified `documento_deuda_id`

### Requirement: EPIC-01 Wallet funnel events are recorded without personal data
The system SHALL record onboarding and checkout events with internal correlation identifiers and timestamps, without identity documents or credentials, so product metrics can be derived.

#### Scenario: Onboarding or checkout step is observed
- **WHEN** onboarding starts, a step completes, checkout begins, or a payment outcome is persisted
- **THEN** one event with its internal correlation and timestamp is recorded without personal data

#### Scenario: A payment outcome is revisited
- **WHEN** a user refreshes a completed payment or a duplicate callback is observed
- **THEN** the same payment outcome is not recorded or counted twice

### Requirement: W3-01 Demo uses a mock QR
The system SHALL create and resolve mock QR payloads through the backend and SHALL present the returned `qrId`, merchant, optional fixed amount, and expiry as mock QR data.

#### Scenario: Payer resolves a mock QR
- **WHEN** the payer submits a payload created by the mock
- **THEN** the backend resolves it through the mock and returns its merchant/amount details for review

#### Scenario: QR is invalid, expired, or mismatched
- **WHEN** the mock rejects the QR
- **THEN** the backend preserves the API error and creates no payment

### Requirement: W3-02 Mock QR does not claim to be a debt document
The system SHALL NOT claim that the mock validates a W3 debt document or enforces one-payment-per-debt when its QR contract contains only mock merchant, amount, and expiry data.

#### Scenario: Demo associates a local label with a QR
- **WHEN** a display label is associated with a mock `qrId`
- **THEN** that association remains non-financial metadata and is identified as a demo limitation relative to W3

### Requirement: W3-03 Payment request and response use the mock contract
The system SHALL send the documented mock payment fields and SHALL associate the returned mock payment ID with the request without asserting that the mock received a debt-document ID.

#### Scenario: Mock creates a payment
- **WHEN** `POST /payments` accepts `walletId`, `recipient`, `amountCents`, `currency`, `qrId`, and `Idempotency-Key`
- **THEN** the backend retains the returned `paymentId` and status as the payment reference for later queries

#### Scenario: Local debt ID is not part of the mock request
- **WHEN** the app associates a demo label with the payment
- **THEN** it does not add undocumented `documento_deuda_id` fields to the mock payload or claim provider validation of that ID

### Requirement: W3-04 Mock payment state is re-queryable
The system SHALL use the mock's payment query, event delivery, or resolve operation as the source of payment state after creation.

#### Scenario: User reloads a payment view
- **WHEN** a user reloads a view for a known mock `paymentId`
- **THEN** the app re-queries the mock and does not treat browser-only status as financial truth

### Requirement: W3-05 Test payment views are responsive and explicit
The system SHALL label the payment flow `Modo prueba` and render payment details and states legibly at 360 px and 1280 px viewport widths.

#### Scenario: Payment state is rendered
- **WHEN** a mock payment is `PENDING`, `SUCCEEDED`, `REJECTED`, or already `REVERSED`
- **THEN** the UI shows a clear Spanish label and the raw mock status, and color is not the sole state indicator

### Requirement: W3-06 Mock statuses are displayed without story-state claims
The system SHALL display the mock's `PENDING`, `SUCCEEDED`, `REJECTED`, or returned `REVERSED` status without claiming it is a persisted W3 debt state.

#### Scenario: Mock payment is pending
- **WHEN** the mock payment is `PENDING`
- **THEN** no success receipt or debt-paid claim is shown

#### Scenario: Mock payment has a final status
- **WHEN** the mock payment is `SUCCEEDED`, `REJECTED`, or already `REVERSED`
- **THEN** the UI shows the exact provider-reported status and does not convert it to a W3 debt transition

#### Scenario: QR expires before payment creation
- **WHEN** the mock returns `410 QR_EXPIRED` while resolving or paying a QR
- **THEN** the UI reports an expired QR and does not label the payment as `EXPIRED`
