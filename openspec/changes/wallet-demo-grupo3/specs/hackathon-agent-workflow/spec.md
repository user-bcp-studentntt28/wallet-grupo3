# Spec Delta

## Purpose

Coordinate the Wallet Perú hackathon change through OpenSpec and five CrewAI
roles with explicit human approval, constrained MCP access, and honest evidence.

## ADDED Requirements

### Requirement: HA-01 OpenSpec change traces the product stories
The team SHALL maintain a spec-driven OpenSpec change for the Wallet Perú demo whose requirements trace to the epic and W1-W6 user stories.

#### Scenario: Proposal is listed for review
- **WHEN** the team creates `wallet-demo-grupo3` under the initialized repository OpenSpec root
- **THEN** `openspec list` shows the active change and its proposal, specs, design, and tasks remain available for review

#### Scenario: Product source conflicts with the old hackathon draft
- **WHEN** the hackathon acceptance draft conflicts with `docs/userstories/`
- **THEN** the stories and epic remain the product sources of truth and the conflict is corrected or explicitly tracked, not silently copied into the spec

### Requirement: HA-02 Scope approval blocks implementation
The workflow SHALL present a versioned scope proposal to a human and SHALL NOT start architecture or implementation tasks until that human explicitly approves that version.

#### Scenario: Human approves a proposal
- **WHEN** the designated human records approval for a specific proposal version
- **THEN** only tasks within that approved scope may proceed

#### Scenario: Proposal is rejected, changed, or unanswered
- **WHEN** the human rejects the proposal, requests material changes, or does not respond
- **THEN** implementation remains blocked and the proposal is revised or the run stops

### Requirement: HA-03 CrewAI uses the five assigned roles sequentially
The workflow SHALL execute Product Owner, Arquitecto/a, AI Engineer, QA & Security, and Presenter / Timekeeper as distinct sequential responsibilities.

#### Scenario: One approved increment passes through the crew
- **WHEN** an increment is approved for work
- **THEN** each role receives the approved sources and prior relevant deliverable and produces its defined output before the next role starts

#### Scenario: A role reports a blocking condition
- **WHEN** a role identifies missing approval, contract, or decision
- **THEN** dependent work is blocked rather than fabricated or implicitly approved

### Requirement: HA-04 Agent outputs remain tied to Wallet Perú requirements
Every agent deliverable SHALL identify relevant epic, W1-W6, or OpenSpec requirement IDs and SHALL distinguish source facts, proposals, unresolved decisions, and executed evidence.

#### Scenario: Agent lacks a required source
- **WHEN** required story, criteria, approved proposal, contract, or implementation evidence is absent from context
- **THEN** the agent identifies the missing source and does not claim it inspected or verified it

### Requirement: HA-05 MCP tools for CrewAI are local and read-only
The CrewAI runtime SHALL use only explicitly allow-listed local MCP tools for read-only group 3 mock queries, and SHALL NOT route application payments or state-changing provider operations through an agent.

#### Scenario: Agent queries approved mock context
- **WHEN** an authorized agent needs scenarios, a test wallet, or a payment status
- **THEN** it may invoke the corresponding read-only MCP tool restricted to the group 3 service

#### Scenario: Agent requests a write or arbitrary destination
- **WHEN** an agent requests a payment mutation, group reset, shell execution, or arbitrary URL
- **THEN** the MCP/runtime rejects the operation and reports the denial

### Requirement: HA-06 QA evidence reports actual execution
The QA role SHALL label every criterion as `APROBADO`, `FALLIDO`, `NO EJECUTADO`, or `BLOQUEADO` based on supplied observable evidence.

#### Scenario: Test has not been executed
- **WHEN** only a test proposal or model-generated analysis is available
- **THEN** its state is `NO EJECUTADO` and it is not presented as a pass

#### Scenario: A criterion fails or is blocked
- **WHEN** observed output differs from expected behavior or a precondition is missing
- **THEN** QA records the failure or blocker with its criterion ID and evidence

### Requirement: HA-07 Jira issue creation requires a separate approval
The OpenSpec workflow SHALL NOT create Jira issues unless a Jira integration and explicit human authorization are provided separately.

#### Scenario: OpenSpec artifacts are drafted
- **WHEN** the team creates or revises proposal, specs, design, or tasks
- **THEN** no Jira project or issue is modified

### Requirement: HA-08 Each CrewAI role receives its specialized skill
The workflow SHALL provide a role-specific skill for each of the five required agents and load that skill into the agent's instructions when it is constructed.

#### Scenario: All five agents are constructed
- **WHEN** the runner constructs Product Owner, Arquitecto/a, AI Engineer, QA & Security, and Presenter / Timekeeper
- **THEN** each agent receives its matching skill together with the shared Wallet Perú rules

#### Scenario: A role skill cannot be loaded
- **WHEN** a required skill is missing, unreadable, or empty
- **THEN** agent construction fails explicitly and the workflow does not continue with generic instructions

### Requirement: HA-09 Final demo approval belongs to a human Product Owner
The workflow SHALL require a human Product Owner's explicit final decision after implementation, QA, and Presenter deliverables before declaring the demo ready.

#### Scenario: Final deliverables are ready for review
- **WHEN** implementation evidence, QA results, known gaps, and the Presenter demo report are available
- **THEN** the workflow presents them with the approved scope version and waits for a human Product Owner decision

#### Scenario: Final approval is missing or rejected
- **WHEN** the human Product Owner rejects the result or has not decided
- **THEN** the demo remains not ready, and no CrewAI agent's output is treated as approval

### Requirement: HA-10 Guardrails gate input, routes, and output
The demo SHALL apply the repository guardrail pattern (input, tool/route policy, and output rules with rule codes) to every backend call to the mock and SHALL keep every mock operation classified in a published feature map.

#### Scenario: Operation is not mapped or is prohibited
- **WHEN** the backend or an agent requests an operation that is unmapped, `/control/reset`, or a reversal
- **THEN** the guardrail denies it by default with its rule code and no request reaches the mock

#### Scenario: State-changing operation lacks human confirmation
- **WHEN** a payment, manual KYC decision, event control, or settlement alteration is requested without explicit confirmation
- **THEN** the guardrail blocks it with `DEMO-TOOL-03` and no request reaches the mock

#### Scenario: Input or response carries sensitive data
- **WHEN** a KYC document is not `TEST-`-prefixed or contains a secret or card pattern, or a mock response contains one
- **THEN** the guardrail blocks it with its `DEMO-IN`/`DEMO-OUT` rule code and the data is not forwarded or returned to the browser

#### Scenario: Feature map covers the contract
- **WHEN** the OpenAPI contract of group 3 is compared with the feature map
- **THEN** every operation is classified exactly once as `ALLOW`, `CONFIRM`, or `DENY` with its criterion and task
