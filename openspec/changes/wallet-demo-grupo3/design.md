# Design

## Context

See [proposal.md](./proposal.md) for motivation and scope. The repository has
placeholders for three browser applications and backend services. The existing
`docs/hackaton/criterios-de-aceptacion.md` describes the API-backed demo; the
six `docs/userstories/` stories remain the broader product target.

The group-3 OpenAPI supports KYC, QR creation/resolution, payments, callbacks,
support cases, ledger, settlements, and reconciliation. `POST /payments`
requires `Idempotency-Key` and accepts `walletId`, `recipient`, and
`amountCents`; it also supports `currency`, test `scenario`, and optional
`qrId`. Payment results use `PENDING`, `SUCCEEDED`, `REJECTED`, or
`REVERSED`. The API does not accept a `documento_deuda_id`; a mock QR validates
its own merchant and amount but does not prove that it represents a debt
document from W3.

## Goals / Non-Goals

**Goals:**

- Deliver a browser → backend adapter → group-3 mock demonstration using the
  endpoints and fields actually declared by the OpenAPI.
- Keep the mock authoritative for demo wallets, balances, payment IDs/statuses,
  provider events, and ledger; keep the frontend away from the mock directly.
- Preserve a clear trace from each demo criterion to W1-W6 and label the full
  story requirements not demonstrated as `POSTERIOR` or `BLOQUEADO`.
- Give each of the five CrewAI roles a specialized skill file that is loaded
  into its agent instructions, and enforce initial and final human approval.
- Keep CrewAI/MCP outside the runtime path that creates or resolves payments.

**Non-Goals:**

- Claiming that a mock `qrId` is a W3 debt-document ID or that this demo
  completes every requirement in the six product stories.
- Creating an application-side financial ledger, duplicate wallet balance, or
  payment-status authority.
- Calling the mock's reversal API; W5 explicitly excludes reversals, refunds,
  and disputes from the product scope.
- Connecting real payment rails, real Google identities, or real customer data.
- Letting an LLM, CrewAI agent, MCP tool, or browser authorize a payment.

## Decisions

### 1. One web demo → one backend adapter → group-3 mock

Deliver one responsive web experience with Registro, Pagos y QR, and Operaciones
sections, backed by one lightweight backend adapter. The browser calls only that
backend; the backend validates requests and calls the fixed group-3 mock routes.
Do not require three separate browser applications, a set of microservices, or
a new API gateway for this hackathon demo. Reuse an existing workspace only
where it keeps implementation smaller and follows its local rules.

Direct browser-to-mock calls are rejected because they expose the upstream
service and bypass backend validation and error handling.

### 2. The mock owns demo financial state

Do not create local financial tables or a second payment ledger for this demo.
The backend maps product-facing requests onto the mock's exact fields and
returns the mock's persisted state. It may keep minimal non-financial demo
evidence: a display reference associated with `qrId` and `paymentId`, internal
correlation IDs, and local capture timestamps for the acceptance criteria. This
evidence must not store personal documents or secrets, be represented as
provider-originated data, or become a second source of financial truth.

Use `wallet-demo` and `merchant-demo` for the seeded payment walkthrough. Send
integer PEN cents and the same `Idempotency-Key` with an identical payload on
retry. Do not expose the mock's `scenario` switch as an ordinary payer control;
keep it in a clearly separated test/facilitator control. A payment normally
starts `PENDING`, including the `APPROVED` test scenario, and must be resolved
through the contract's event/resolve flow before presenting its final state.

### 3. Map the API contract without pretending it is W3

Create and resolve the mock QR through the backend. For a payment, send only
the fields the mock supports: `walletId`, `recipient`, `amountCents`,
`currency`, optional `scenario`, optional `qrId`, and required
`Idempotency-Key`. Map a local demo display reference to the mock's `qrId` and
`paymentId` only for navigation and evidence.

The UI translates `PENDING`, `SUCCEEDED`, `REJECTED`, and any returned
`REVERSED` state to clear Spanish labels, while preserving the raw status in
evidence. The mock's `APPROVED` scenario is not a final `SUCCEEDED` payment.
Treat QR expiry (`410`) as a QR error, not a payment status. Do not call the
reversal API; if a shared-group payment is already `REVERSED`, display the
returned state and do not hide or mutate it. This permits a real API-backed demo
while making the missing debt-document field an explicit W3 limitation rather
than a false integration blocker or a false claim of full W3 compliance.

### 4. CrewAI and MCP are a gated development workflow

Retain the five requested roles: Product Owner, Architect, AI Engineer,
QA & Security, and Presenter / Timekeeper. CrewAI tasks run in a defined
sequence with the Product Owner's explicit scope approval as a prerequisite for
implementation. An agent reports evidence and blockers; it cannot approve its
own scope, deploy code, or alter payment outcomes.

The local MCP is available only to explicitly configured agent tools for
bounded, read-only group-3 queries. It is not called by the web or backend
payment flow and has no authority over balances, payment status, resets, or
scope. Align `agents/common.py` and the role-specific prompts with the demo's
mock authority. Store one specialized skill per role under `agents/skills/` and
load the skill text when each CrewAI agent is constructed; Markdown files that
are not loaded are not considered integrated skills.

HA-02 is the initial human approval of the versioned scope. Add a distinct final
gate: after implementation, QA, and Presenter deliverables, a human Product
Owner reviews the version, acceptance evidence, known gaps, and test results.
The Product Owner CrewAI agent cannot satisfy this gate. A rejection or missing
approval keeps the demo from being declared ready.

### 5. Separate product requirements from the earlier demo draft

Use the six stories as the product target and
`docs/hackaton/criterios-de-aceptacion.md` as the demo-specific acceptance
profile. Align that profile to the supported KYC, payment, and reconciliation
responses; call out the local `qrId`/`paymentId` mapping and absence of a
provider-visible debt ID; and remove W5 reversal actions from the demo. Keep
unsupported story requirements labeled `POSTERIOR` or `BLOQUEADO`; do not change
the source stories or create Jira issues in this workflow.

## Risks / Trade-offs

- [A mock QR is not a W3 debt document] → Keep the local display-reference
  mapping explicitly non-financial and label full debt-document behavior
  `POSTERIOR`; never claim the mock validated a debt ID.
- [The mock has mutable shared group state and its own wallet ledger] → Use
  test-only identities and amounts, never reset automatically, and disclose that
  other group members' operations can affect reported results.
- [The mock exposes reversal operations that W5 forbids] → Do not invoke those
  endpoints in the demo; surface any `REVERSED` state already present as
  provider-reported evidence.
- [Test scenarios can be confused with real user actions] → Keep controls for
  `scenario` and event delivery separate, visibly marked, and excluded from
  normal payer flows.
- [The old agent instructions can conflict with the API-backed demo] → Align
  shared and per-role skills before enabling the CrewAI implementation workflow.
- [A final agent report could be mistaken for approval] → Require a separate
  human Product Owner sign-off after QA and Presenter outputs.
- [An implementation may accidentally add reversal or real-money behavior] →
  Keep W5 exclusions in API contracts, UI, agent context, and QA checks.

## Migration Plan

1. Approve the revised demo scope before implementation; retain the original
   W1-W6 stories as product targets.
2. Align the hackathon acceptance criteria and agent rules with the actual
   OpenAPI, including demo gaps and the W5 no-reversal decision.
3. Add the five role skills and the final human Product Owner gate to the
   CrewAI runner.
4. Implement and test the API adapter using the group's supported routes and
   test-only identities. Do not call the group reset automatically.
5. Run focused API-contract, integration, and browser-flow checks. Label every
   story requirement without evidence `POSTERIOR`, `NO EJECUTADO`, or `BLOQUEADO`.
6. Obtain final human Product Owner approval of the implementation/evidence
   before declaring the demo ready. No production deployment is part of this
   change.
