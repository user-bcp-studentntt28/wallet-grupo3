# Tasks

## 1. Scope and acceptance

- [x] 1.1 Obtain explicit human approval of the versioned W1-W6 demo scope before implementation; verify the decision identifies the approved version, `DEMO` criteria, and `POSTERIOR`/`BLOQUEADO` gaps. Human approval recorded in this conversation on 2026-10-23 for the current `wallet-demo-grupo3` version.
- [x] 1.2 Align `docs/hackaton/criterios-de-aceptacion.md` with the group-3 OpenAPI: preserve source stories, state that no `documento_deuda_id` is sent, use mock statuses and group-wide reconciliation, and remove demo reversal actions; verify every W1-W6 source criterion is mapped and no unsupported API behavior is claimed. Verified the six traceability rows and `git diff --check` (exit 0).

## 2. Simple web and backend boundary

- [x] 2.1 Build one responsive web experience with Registro, Pagos y QR, and Operaciones sections plus one lightweight backend adapter to the fixed group-3 mock; verify browser requests go only to the backend, arbitrary upstream destinations are rejected, and API errors are not converted into success-shaped fallbacks. Verified with 7 focused tests, browser navigation, live group-3 `/scenarios` response (15 options across 3 categories), 404 for arbitrary upstream paths, and preserved 503/502 failures.
- [x] 2.2 Add minimal non-financial demo evidence for correlation IDs, local capture timestamps, and `qrId`/`paymentId` references; verify export contains no document values, credentials, or locally invented financial state. Verified with an allow-listed in-memory evidence store, downloadable JSON export, and a test asserting resource references, timezone-aware local timestamps, and absence of document, credential, status, amount, or balance fields.

## 3. W1 — Test onboarding

- [ ] 3.1 Implement the guided KYC form using only `documentType: TEST` and `document` values prefixed with `TEST-`; verify invalid values send no request, the UI identifies KYC as simulated, and `APPROVED`, `REJECTED`, `MANUAL_REVIEW`, and `UNAVAILABLE` display the mock's actual outcomes.
- [ ] 3.2 Implement the facilitator-confirmed manual decision and mock wallet query; verify `MANUAL_REVIEW` remains pending until a human decision and wallet status/balance always come from the mock.
- [ ] 3.3 Record and export the W1 onboarding trace without personal data; verify the responsive flow at 360 px and 1280 px and ensure a new wallet is not shown as funded.

## 4. W2/W3 — QR and mock payment

- [ ] 4.1 Implement QR creation and resolution through the backend, including fixed/open amount handling; verify invalid, mismatched, and expired QR responses are shown as API errors and a QR expiry is not presented as a payment status.
- [ ] 4.2 Implement explicit payment confirmation with only supported mock fields and required `Idempotency-Key`; verify a fixed/open QR sends its `qrId`, no `documento_deuda_id` is sent, and the app creates no local financial reservation or ledger.
- [ ] 4.3 Implement pending-to-final status refresh, receipt, wallet history, and the local merchant-session view; verify `PENDING` is not success, final status and balance are re-queried from the mock, and local timestamps/references are labeled as demo evidence.

## 5. W4/W5 — Idempotency and support

- [ ] 5.1 Implement repeat requests and duplicate event handling using the same key and payload; verify an identical retry returns the same mock payment, a changed payload surfaces `409 IDEMPOTENCY_CONFLICT`, and duplicate event delivery creates no second payment presentation.
- [ ] 5.2 Implement safe guidance for `503`, `504`, QR expiry, rejection, and unresolved `PENDING`; verify uncertain outcomes can be queried/resolved without an automatic second payment and `PROVIDER_ERROR` is not shown as a completed transaction.
- [ ] 5.3 Implement read-only support-case views and exclude reversal actions; verify support uses returned mock details, no reversal endpoint is called, and any already-`REVERSED` record is displayed only as a mock-reported status.

## 6. W6 — Group reconciliation

- [ ] 6.1 Implement the mock-backed settlements, ledger, reconciliation, and incident views; verify the UI displays `MATCHED`/`DIFFERENCES`, returned incident IDs/reasons/statuses, and group-wide scope without claiming provider-date or bank reconciliation.
- [ ] 6.2 Add the optional `AMOUNT`/`CLEAR` report-difference walkthrough behind explicit facilitator confirmation; verify reconciliation opens and resolves the returned incident without changing wallet or ledger values, and never calls `/control/reset`.

## 7. CrewAI skills, MCP, and approval gates

- [ ] 7.1 Create one specialized skill file under `agents/skills/` for Product Owner, Arquitecto/a, AI Engineer, QA & Security, and Presenter / Timekeeper; verify each skill defines its role-specific sources, responsibilities, deliverable, and demo boundaries.
- [ ] 7.2 Load each role's skill when constructing its CrewAI agent and align shared/role instructions with mock authority, API statuses, no debt-ID claim, and no reversal; verify all five agent backstories include the correct skill and `python tools\verify.py` passes.
- [ ] 7.3 Implement the sequential CrewAI runner with the initial human scope gate; verify missing, rejected, or changed approval blocks downstream work and the Product Owner agent cannot approve its own proposal.
- [ ] 7.4 Connect the local MCP to explicitly allow-listed, read-only group-3 query tools used by CrewAI; verify a real agent invocation consumes a tool response and write operations, reset, shell, and arbitrary destinations are denied.
- [ ] 7.5 Implement the final human Product Owner gate after implementation, QA, and Presenter outputs; verify the decision records the scope version and evidence and that missing/rejected approval prevents a `ready` result.

## 8. Integrated demo and final review

- [ ] 8.1 Run the browser → backend → group-3 mock walkthrough for approved W1-W6 demo criteria; verify each result is recorded as `APROBADO`, `FALLIDO`, `NO EJECUTADO`, or `BLOQUEADO` with observable evidence and no fabricated API results.
- [ ] 8.2 Rehearse the Presenter / Timekeeper walkthrough and capture its actual duration, CrewAI/MCP evidence, known gaps, and safe fallback; verify the report distinguishes measured results from estimates.
- [ ] 8.3 Obtain final explicit human Product Owner approval after QA and presentation evidence are complete; verify the decision references the delivered version and unresolved gaps, and do not declare the demo ready if approval is absent or rejected.
