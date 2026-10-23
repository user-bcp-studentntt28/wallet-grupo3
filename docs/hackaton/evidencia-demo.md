# Evidencia de la corrida integrada (tarea 8.1)

Corrida del 2026-10-23 contra el mock real del grupo 3: navegador → backend
(`demo_server.py`) → mock. Estados según HA-06: `APROBADO`, `FALLIDO`,
`NO EJECUTADO`, `BLOQUEADO`. Solo se marca `APROBADO` con evidencia observada
(navegador, llamada real o prueba automatizada citada). Las pruebas automatizadas
son `tests/test_demo_routes.py`, `tests/test_demo_guardrails.py` y
`tests/test_wallet_demo_server.py` (45 OK).

> El mock es compartido: sus pagos e incidencias pueden ser de otros integrantes.
> Los pagos de prueba de esta corrida se finalizaron; las incidencias propias
> quedaron cerradas. La conciliación sigue en `DIFFERENCES` por pagos ajenos.

## Criterios funcionales W1–W6

| ID | Estado | Evidencia observada / nota |
|---|---|---|
| W1-01 | APROBADO | Pasos y «siguiente acción» actualizados en el navegador. |
| W1-02 | APROBADO | `12345678` bloqueado (`DEMO-IN-02`) sin petición al mock; `TEST-…` enviado solo con `documentType: TEST`. |
| W1-03 | APROBADO | `APPROVED` → `ACTIVE`, IDs, wallet consultada, saldo S/ 0.00 con aviso «sin fondos». |
| W1-04 | APROBADO | `MANUAL_REVIEW` → `PENDING`; sin confirmación no se envía; con confirmación → `ACTIVE`. |
| W1-04b | NO EJECUTADO | No se verificó que la decisión actualice el caso de soporte `KYC_REVIEW`. |
| W1-05 | APROBADO | `REJECTED` → `REJECTED`; `UNAVAILABLE` → `503 KYC_UNAVAILABLE`, sin éxito anunciado. |
| W1-06 | APROBADO | Exportación con `ONBOARDING_STARTED/STEP_COMPLETED/COMPLETED`, `sessionId`, wallet y hora local; sin documento. |
| W2-01 | APROBADO | 6 importes inválidos (vacío, 0, 1.234, abc, -5, 1000000.01) bloqueados sin petición. |
| W2-02 | APROBADO | Monto > disponible y wallet sin fondos bloqueados. |
| W2-02b | NO EJECUTADO | Wallet no activa (`PENDING`/`REJECTED`) y saldo insuficiente devuelto por el mock. |
| W2-03 | APROBADO | `202 PENDING`, ID de pago, sin comprobante antes de confirmar. |
| W2-04 | APROBADO | Evento entregado → reconsulta: `SUCCEEDED` (comprobante, saldo 700→699) y `REJECTED` (sin cargo). |
| W2-05 | APROBADO | Entrega repetida sin cambio contradictorio. `REVERSED` no se observó. |
| W2-06 | APROBADO | Historial desde el mock, también tras recargar. |
| W2-07 | APROBADO | `CHECKOUT_STARTED/CONFIRMED`, `PAYMENT_ACTIVATED` una sola vez por pago (3 pagos, 3 activaciones únicas). |
| W3-01 | APROBADO | Payload `qrmock:` + imagen QR; resolución pegando el payload. |
| W3-02 | APROBADO | QR fijo bloquea el monto; el pago envía `qrId` (corregido durante la corrida). |
| W3-03 | APROBADO | Payload no `qrmock:` rechazado; `410 QR_EXPIRED`; `409 QR_PAYMENT_MISMATCH` mostrado. |
| W3-04 | APROBADO | Vista de comercio: referencia, QR, estado del mock; «No entregar» mientras `PENDING`. |
| W3-05 | APROBADO | Filtro por referencia y por fecha local (hoy = 1, 2000-01-01 = 0). |
| W3 (deuda) | BLOQUEADO | El mock no recibe `documento_deuda_id`; `POSTERIOR`. |
| W4-01 | APROBADO | Clave y contenido conservados tras recargar; reintento con la misma clave. |
| W4-02 | APROBADO | Reintento → `HTTP 200` mismo pago. Ledger no se comparó antes/después. |
| W4-03 | APROBADO | Monto distinto → `409 IDEMPOTENCY_CONFLICT`, sin clave nueva automática. |
| W4-04 | APROBADO | Primera entrega y repetición (`duplicate`) con reconsulta del pago. |
| W4-05 | APROBADO | Traza con `attempt` ORIGINAL/RETRY, `idempotencyKey`, `eventId`, `httpStatus`. |
| W4-06 | NO EJECUTADO | No se contrastó la conciliación con la traza de reintentos. |
| W5-01 | APROBADO | `504` conserva el `paymentId`; sin segundo cobro. |
| W5-01b | NO EJECUTADO | Falla de red sin respuesta (solo cubierta por código, no ejecutada). |
| W5-02 | APROBADO | Escenario `PROVIDER_ERROR` → `503 PROVIDER_UNAVAILABLE` (código real) con nuevo intento controlado. |
| W5-03 | APROBADO | Resolver `PENDING` → `escalated:true` y un único caso `PROVIDER_PENDING` tras dos resoluciones. |
| W5-04 | APROBADO | Guía distinta para rechazo, 503, 504, pendiente y éxito. |
| W5-05 | APROBADO | Sin acción de reverso/devolución/disputa en la UI. |
| W5-06 | APROBADO | Reversos y reset `DENY` (`DEMO-TOOL-02`); rutas no expuestas (pruebas). |
| W5-07 | APROBADO | Casos con recurso, motivo y estado; consulta registrada como `SUPPORT_CASES_VIEWED`. |
| W6-01 | APROBADO | `DIFFERENCES` real; liquidaciones, ledger e incidencias consultables. |
| W6-02 | APROBADO | Sin confirmación → `403 DEMO-TOOL-03`; `AMOUNT` sobre pago propio → incidencia. |
| W6-03 | APROBADO | Misma incidencia `OPEN` → `RESOLVED` tras `CLEAR`; sin `/control/reset`. |
| W6-04 | APROBADO | Resumen: pagos con/sin diferencias, incidencias abiertas/resueltas, wallet y huérfanos por separado. |
| W6-05 | APROBADO | Ejecuciones con hora local y filtro por fecha. |

## IA-xx (CrewAI, MCP, aprobaciones)

| ID | Estado | Evidencia observada / nota |
|---|---|---|
| IA-01 | NO EJECUTADO | Runner CrewAI con cinco roles probado en dry-run y con LLM guionado; falta una corrida con modelo real (Copilot sin sesión autenticada). |
| IA-02 | APROBADO | Sin `evidence/scope_approval.json` el runner devuelve `BLOQUEADO` (código 2); pruebas cubren rechazo/versión cambiada/aprobador agente. |
| IA-03 | APROBADO | El registro exige versión (`wallet-demo-grupo3@565f7500b3ae`), decisión, aprobador humano y hora (pruebas). |
| IA-04 | APROBADO | MCP real `GET /scenarios` por stdio (200); un agente con LLM guionado lo consumió. No se probó con un modelo real. |
| IA-05 | APROBADO | Reset/reversos `DEMO-TOOL-02`, escrituras `DEMO-TOOL-03`, URL o herramienta ajena `DEMO-TOOL-01`; fallos del mock informados como fallo. |
| IA-06 | APROBADO | El navegador solo llama a `/api/*`; destino fijo; sin proxy arbitrario (pruebas). |
| IA-07 | NO EJECUTADO | Falta la aprobación final de una persona (Product Owner). Ver `docs/hackaton/runner.md`. |

## Hallazgos corregidos durante la corrida

- La resolución del QR del mock no devuelve su ID: el pago iba sin `qrId`. Ahora se deriva de `qrmock:<id>`.
- El 503 real es `PROVIDER_UNAVAILABLE` (no `PROVIDER_ERROR`); la guía depende del estado HTTP.
- El 504 mostraba el `status` interno como resultado; ahora se rotula «junto al error».
- El resumen de conciliación no separaba pagos con/sin diferencias ni incidencias abiertas/resueltas (W6-04).
