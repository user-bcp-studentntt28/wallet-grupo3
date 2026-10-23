# Spec Delta

## Purpose

Define how the demo presents group-3 settlement, ledger, reconciliation, and
incident data without claiming daily or bank reconciliation.

## ADDED Requirements

### Requirement: W6-01 Reconciliation displays the mock result
The system SHALL run the documented mock reconciliation and display its returned status and differences without recalculating financial truth locally.

#### Scenario: Reconciliation finds no differences
- **WHEN** `POST /reconciliations` returns `MATCHED`
- **THEN** the UI displays `MATCHED` and the returned empty differences list

#### Scenario: Reconciliation finds differences
- **WHEN** `POST /reconciliations` returns `DIFFERENCES`
- **THEN** the UI displays the returned incidents and does not modify payment, wallet, or ledger data

### Requirement: W6-02 Settlement and ledger views use mock responses
The system SHALL display settlement and ledger data returned by the mock and distinguish those group-wide records from local demo evidence.

#### Scenario: Operations views settlements
- **WHEN** the backend queries `GET /settlements`
- **THEN** the UI displays the returned group report, including pending or rejected records, without adding local payments

#### Scenario: Operations views the ledger
- **WHEN** the backend queries `GET /ledger`
- **THEN** the UI displays the returned entries and does not create or edit ledger rows

### Requirement: W6-03 Incidents preserve mock identity and status
The system SHALL display reconciliation incidents using the mock's returned resource, reason, ID, and `OPEN` or `RESOLVED` status.

#### Scenario: Operations queries incidents
- **WHEN** the backend queries `GET /reconciliations/incidents`
- **THEN** the UI displays the returned incident records without inventing a resolution

#### Scenario: The same difference is reconciled again
- **WHEN** the mock sees the same resource and reason on a later reconciliation
- **THEN** the UI retains the returned incident ID and shows the status returned by the mock

### Requirement: W6-04 Summary counts reflect observed reconciliation data
The system SHALL distinguish payment counts from incident counts and derive any displayed totals only from returned mock data or explicitly labeled local run evidence.

#### Scenario: Operations views a reconciliation summary
- **WHEN** a reconciliation result and incident list are available
- **THEN** the summary counts returned payments and incidents separately and identifies its data source

### Requirement: W6-05 Group-wide reconciliation is not presented as daily or bank reconciliation
The system SHALL disclose that the mock reconciles all group-3 data and SHALL NOT claim provider-date, channel, daily-cutoff, or external-bank filtering that the API does not offer.

#### Scenario: A local reconciliation timestamp is displayed
- **WHEN** the demo records when an operator ran a reconciliation
- **THEN** the timestamp is labeled as local capture time, not a provider transaction date

### Requirement: W6-06 Mock report alterations require a human facilitator
The system SHALL require explicit human facilitator confirmation before using `/control/settlements` to create or clear a reconciliation test difference.

#### Scenario: Facilitator confirms a test difference
- **WHEN** a facilitator confirms an `AMOUNT` alteration for an existing test payment
- **THEN** the backend uses the documented mock control, reconciliation reports the returned difference, and no wallet or ledger value is changed

#### Scenario: Facilitator clears a test difference
- **WHEN** a facilitator confirms `CLEAR` for the altered test payment and reconciliation is rerun
- **THEN** the UI shows the incident status returned by the mock, including `RESOLVED` when reported

#### Scenario: Facilitator has not confirmed a test alteration
- **WHEN** no explicit human confirmation is recorded
- **THEN** the demo sends no `/control/settlements` request and does not call `/control/reset`
