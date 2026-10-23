# Proposal

## Why

Las historias W1-W6 describen el producto objetivo, pero el hackaton debe mostrar
una demo funcional con el mock disponible del grupo 3. La demo debe usar el
contrato real del mock y declarar con precisión qué requisitos de las historias
quedan para después, sin editar ni presentar las historias originales como
cumplidas.

## What Changes

- Implementar una web sencilla con secciones Registro, Pagos y QR, y
  Operaciones, más un backend adaptador que invoque el mock del grupo 3; el
  navegador y CrewAI no llaman al proveedor como ruta financiera.
- Usar los endpoints de KYC, QR, pagos, eventos, soporte e informes que declara
  el OpenAPI. Para `POST /payments`, usar `Idempotency-Key` y los campos
  `walletId`, `recipient`, `amountCents`, `currency` y `qrId` cuando aplique.
- Tratar el mock como fuente autoritativa de wallets, saldos, pagos, estados,
  eventos y ledger en la demo. La app puede guardar asociaciones no financieras
  y marcas de tiempo locales para evidencia/analítica básica; no guardará datos
  personales ni afirmará que el mock recibió o validó un `documento_deuda_id`,
  que no existe en su contrato.
- Trazar cada historia W1-W6 a criterios de demo `DEMO`, `POSTERIOR` o
  `BLOQUEADO`; mantener intactas las historias originales.
- Mantener los cinco roles CrewAI, con un playbook de skill especializado por
  rol cargado realmente al construir cada agente, y MCP local de uso acotado.
- Conservar dos gates distintos: aprobación humana inicial del alcance y
  aprobación humana final del Product Owner después de cambios y QA.
- No usar el endpoint de reversos durante la demo: W5 excluye extornos,
  devoluciones y disputas aunque el mock tenga esa capacidad.
- No crear tickets Jira. No conectar dinero real, datos personales reales ni
  proveedores reales.

No se crean issues de Jira en este cambio. OpenSpec será la fuente del plan; la
creación de tickets Jira requiere una integración y autorización aparte.

## Capabilities

### New Capabilities

- `wallet-onboarding`: recorrido KYC de prueba del mock y visualización de sus
  estados de wallet; el onboarding completo de W1 queda trazado por separado.
- `qr-debt-payments`: QR del mock, pago asíncrono, recibo e historial según el
  contrato disponible; el vínculo a documentos de deuda reales de W3 queda
  posterior.
- `payment-idempotency`: uso del `Idempotency-Key` del mock y tratamiento de
  callbacks repetidos para W4.
- `payment-failure-support`: estados y errores que expone el mock, con soporte
  de solo lectura y sin invocar reversos, conforme a W5.
- `transaction-reconciliation`: informes e incidencias del mock con límites
  explícitos de alcance grupal para W6.
- `hackathon-agent-workflow`: cinco roles CrewAI, skills cargadas, gates humanos
  inicial/final y acceso MCP acotado a la demo.

### Modified Capabilities

Ninguna. `openspec/specs/` no contiene capacidades existentes.

## Trazabilidad W1-W6

| Fuente | Requisitos OpenSpec | Criterios cubiertos |
|---|---|---|
| W1: Registro y activación | Criterios demo W1-01–W1-06; W1-07 como límite de seguridad | La demo usa KYC de prueba del mock. Identidad propia, Google, biometría, sesiones de 300 s y gestión completa de billeteras siguen en las historias fuente y se etiquetan `POSTERIOR` si no tienen evidencia demo. |
| W2: Pago QR, confirmación e historial | Criterios demo W2-01–W2-07 | Se usan los pagos, estados, saldo, recibo e historial del mock. El mock no recibe `documento_deuda_id`; no se declara cumplido el pago integral de W2. |
| W3: Pago QR de documento de deuda | Criterios demo W3-01–W3-05 | `qrId` enlaza el QR y pago del mock; la referencia local de demo no demuestra una deuda persistida/validada según W3. |
| W4: Idempotencia | Criterios demo W4-01–W4-06 | La demo prueba `Idempotency-Key`, respuesta repetida/conflictiva y entrega duplicada de eventos, según capacidades del mock. |
| W5: Fallas y soporte | Criterios demo W5-01–W5-07 | Se prueban pendiente, rechazo, timeout e investigación disponibles. Reversos, devoluciones y disputas no forman parte de esta demo, conforme a W5. |
| W6: Conciliación | Criterios demo W6-01–W6-05 | Se muestran informes, ledger e incidencias del mock; el resultado puede cubrir todo el grupo y no equivale a una conciliación bancaria/diaria productiva. |
| Epic: Instrumentación de funnel | `EPIC-01` | Eventos de la demo sin datos personales; no se declaran cumplidas metas de negocio trimestrales. |

Los requisitos de workflow `HA-01`–`HA-09` cubren OpenSpec, los gates humanos
inicial/final, cinco roles CrewAI con skills cargadas, trazabilidad de
evidencias, límites MCP y la prohibición de crear tickets Jira sin autorización.

## Impact

- Fuentes de comportamiento: `docs/userstories/epic/peru-wallet-mvp.sp.md` y
  todas las seis historias `docs/userstories/user-stories/*.sp.md`.
- Alineación documental: `docs/hackaton/criterios-de-aceptacion.md`,
  `docs/hackaton/agentes.md` e instrucciones en `agents/`.
- Workspaces existentes, actualmente con placeholders: `apps/payer-web`,
  `apps/merchant-web`, `apps/operations-web`; `services/api-gateway`,
  `services/identity-onboarding-api`, `services/wallet-payments-api` y
  `services/operations-reconciliation-api`; contratos compartidos bajo
  `packages/api-contracts`. La demo usará la superficie más pequeña que respete
  las convenciones del repo, sin exigir tres apps o todos esos servicios.
- Fuente financiera de la demo: el mock del grupo 3. No se implementa una
  segunda base de saldos, pagos o ledger; el almacenamiento local, si se usa,
  se limita a asociaciones y trazas no financieras de la demo.
- El contrato OpenAPI permite QR y pagos con `qrId`, `walletId`, `recipient`,
  `amountCents`, `currency` e `Idempotency-Key`, pero no incluye
  `documento_deuda_id`. La demo no queda bloqueada por esa limitación; el pago
  específico de una deuda conforme a W2/W3 queda expresamente fuera del alcance
  demostrable hasta que exista una API compatible.
- CrewAI, servidor/cliente MCP, GitHub Copilot/OpenSpec, autenticación Google de
  prueba, almacenamiento y pruebas funcionales. Sin proveedores de pago reales,
  Google para cuentas reales, datos personales reales ni dinero real.
