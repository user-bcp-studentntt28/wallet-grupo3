# Mapa de funcionalidades y guardrails — Wallet Perú · Grupo 3

Fuente única de la clasificación: [`demo_guardrails.py`](../../demo_guardrails.py)
(`FEATURE_MAP`). La demo la publica en `/api/guardrails` y en la pestaña
**Operaciones**. Una prueba (`tests/test_demo_guardrails.py`) falla si alguna de
las 32 operaciones del OpenAPI del grupo 3 queda sin clasificar.

Estado: **Hecho** = implementado y probado · **Pendiente** = tarea OpenSpec abierta ·
**Excluido** = fuera de alcance por diseño.

## Funcionalidades por historia

| Historia | Funcionalidad | Operaciones del mock | Ruta backend | Política | Tarea | Estado |
|---|---|---|---|---|---|---|
| Base | Verificar conexión / escenarios | `GET /scenarios`, `GET /health` | `/api/scenarios`, `/api/health` | ALLOW | 2.1 | Hecho |
| Base | Evidencia no financiera exportable | — (local) | `/api/evidence/export` | — | 2.2 | Hecho |
| Base | Mapa y guardrails publicados | — (local) | `/api/guardrails` | — | 2.3 | Hecho |
| W1 | KYC simulado (`TEST-`) | `POST /kyc/verifications` | `/api/kyc` | ALLOW | 3.1 | Hecho |
| W1 | Decisión humana de `MANUAL_REVIEW` | `GET /kyc/verifications/{id}`, `POST …/decision` | `/api/kyc/{id}/decision` | CONFIRM | 3.2 | Hecho |
| W1 | Estado y saldo de wallet | `GET /wallets/{id}` | `/api/wallets/{id}` | ALLOW | 3.2 | Hecho |
| W1 | Traza de onboarding sin datos personales | — (local) | `/api/evidence/export` | — | 3.3 | Hecho |
| W2/W3 | Crear y resolver QR | `POST /qrs`, `POST /qrs/resolve` | `/api/qrs`, `/api/qrs/resolve` | ALLOW | 4.1 | Hecho |
| W2/W3 | Pago con confirmación e `Idempotency-Key` | `POST /payments` | `/api/payments` | CONFIRM | 4.2 | Hecho |
| W2/W3 | Estado, comprobante e historial | `GET /payments`, `/{id}`, `/{id}/receipt`, `POST /control/provider/{id}/complete` | `/api/payments…`, `/api/control/provider/{id}/complete` | ALLOW / CONFIRM | 4.3 | Hecho |
| W4 | Reintento idéntico y evento duplicado | `POST /payments`, `POST /callbacks/payments`, `GET /control/events`, `POST /control/events/{id}/deliver` | `/api/payments`, `/api/callbacks`, `/api/events`, `/api/control/events/{id}/deliver` | CONFIRM | 5.1 | Hecho |
| W5 | Guía ante 503/504/QR vencido/rechazo | `POST /payments/{id}/resolve`, `GET /provider/payments/{id}` | `/api/payments/{id}/resolve`, `/api/provider/payments/{id}` | CONFIRM / ALLOW | 5.2 | Hecho |
| W5 | Soporte de solo lectura | `GET /support/cases`, `GET /reversals/{id}` | `/api/support/cases`, `/api/reversals/{id}` | ALLOW | 5.3 | Hecho |
| W5 | Reversos, devoluciones y disputas | `POST /payments/{id}/reversals` | — | **DENY** | 5.3 | Excluido |
| W6 | Liquidaciones, ledger, conciliación e incidencias | `GET /settlements`, `/ledger`, `/reconciliations/incidents`, `POST /reconciliations` | `/api/settlements`, `/api/ledger`, `/api/incidents`, `/api/reconciliations` | ALLOW | 6.1 | Hecho |
| W6 | Alterar reporte `AMOUNT`/`CLEAR` | `POST /control/settlements` | `/api/control/settlements` | CONFIRM | 6.2 | Hecho |
| Control | Reiniciar datos del grupo | `POST /control/reset` | — | **DENY** | 6.2 | Excluido |
| Control | Datos de otros grupos / uso / logs | `GET /groups`, `/usage`, `/usage/all`, `/logs` | — | **DENY** | — | Excluido |

## Observaciones del mock real (verificadas en vivo)

- `PROVIDER_ERROR` como escenario responde `503 PROVIDER_UNAVAILABLE` (no devuelve ese código); sin operación ni reserva.
- `TIMEOUT_AFTER_PROCESSING` responde `504` con `paymentId`: el pago existe; se consulta o resuelve, no se repite.
- Un pago con escenario `APPROVED` nace `PENDING`; solo pasa a `SUCCEEDED` al entregarse su evento.
- El estado es compartido por todo el grupo: otros integrantes pueden dejar incidencias `STATUS_MISMATCH` abiertas, por lo que la conciliación puede mostrar `DIFFERENCES` sin que la demo lo cause.

## Guardrails aplicados

Siguen el patrón del repositorio (`guardrails/` y `harness/`): fallar antes de
gastar, denegar por defecto y dejar un código de regla.

| Capa | Código | Regla | Dónde se aplica |
|---|---|---|---|
| Entrada | `DEMO-IN-01` | Cuerpo objeto JSON, solo campos permitidos | `POST /api/*` |
| Entrada | `DEMO-IN-02` | `documentType` `TEST` y documento con prefijo `TEST-` (≤ 200) | `POST /api/kyc` |
| Entrada | `DEMO-IN-03` | Sin secretos ni números de tarjeta en el documento (reutiliza `guardrails/input_check.py`) | `POST /api/kyc` |
| Entrada | `DEMO-IN-04` | IDs de recurso `[A-Za-z0-9_-]{1,100}` (sin `..` ni `%2F`) | Toda llamada al mock |
| Entrada | `DEMO-IN-05` | Clave de exactamente 6 dígitos, sin repetidos ni secuencias obvias (111111, 123456) | `POST /api/auth/register` |
| Rutas | `DEMO-TOOL-01` | Operación no mapeada: denegada por defecto | Toda llamada al mock |
| Rutas | `DEMO-TOOL-02` | `DENY`: reset, reversos, datos de otros grupos | Toda llamada al mock |
| Rutas | `DEMO-TOOL-03` | `CONFIRM` sin confirmación humana explícita | Toda llamada al mock |
| Salida | `DEMO-OUT-01` | Respuesta del mock con secreto o PII no llega al navegador | Toda respuesta |

Las denegaciones **no llegan al mock** (probado) y quedan en la evidencia solo
con su código. El runner CrewAI y el MCP (tareas 7.3 y 7.4) reutilizarán estas
mismas reglas más `harness/policies/allowed_tools.json`: las herramientas MCP son
únicamente las marcadas `mcp_read_only` (escenarios, wallet y pago).
