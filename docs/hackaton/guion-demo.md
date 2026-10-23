# Guion de la demo (Presenter / Timekeeper) — para el ensayo 8.2

Los tiempos de esta tabla son **ESTIMADOS**. La columna «Medido» debe completarla
una persona al ensayar con cronómetro; mientras esté vacía, la duración real
**no está medida** y no debe presentarse como tal.

Preparación: `python demo_server.py` → <http://127.0.0.1:8000>. Todo lo que verá la
audiencia usa datos `TEST` del mock del grupo 3 (compartido: los saldos pueden variar).

| # | Bloque | Qué se muestra | Criterios | Estimado | Medido |
|---|---|---|---|---|---|
| 1 | Contexto | Arquitectura navegador → backend → mock; el mock es la autoridad; guardrails | IA-06 | 1:00 | |
| 2 | Registro | `TEST-…` con `MANUAL_REVIEW` → `PENDING` → decisión del facilitador → wallet `ACTIVE` sin fondos | W1-01…06 | 2:00 | |
| 3 | QR y pago | QR de S/ 1.00 con imagen, resolver, confirmar, `PENDING`, saldo reservado | W2, W3 | 2:00 | |
| 4 | Idempotencia | Reintento (mismo pago), conflicto `409`, entrega de evento y repetición | W4 | 1:30 | |
| 5 | Fallas | `PROVIDER_ERROR` (503), `TIMEOUT_AFTER_PROCESSING` (504), QR vencido; guía segura | W5 | 1:30 | |
| 6 | Operaciones | Soporte de solo lectura, conciliación, `AMOUNT`→`CLEAR` con confirmación | W5, W6 | 2:00 | |
| 7 | Guardrails y agentes | Tabla de 32 operaciones; runner bloqueado sin aprobación; MCP de solo lectura | HA-10, IA-01…05 | 1:30 | |
| 8 | Brechas y cierre | W3 sin `documento_deuda_id`; sin reversos; pendientes; aprobación final | 8.3 | 1:00 | |

**Total estimado: 12:30** (suma de estimados; no es una medición).

## Respaldo seguro (si el mock falla o responde lento)

1. Mostrar `docs/hackaton/evidencia-demo.md` (resultados de la corrida del 2026-10-23).
2. Mostrar la tabla de guardrails (no depende del mock) y `python run_crew.py --dry-run`.
3. No simular respuestas: si el mock no responde, decirlo y mostrar el error tal cual.
4. Si hay incidencias abiertas de otros grupos, explicarlo (estado compartido); no borrar datos ni usar reset.

## Brechas conocidas para decirlas en voz alta

- W3 completo (pago de una deuda concreta) es `POSTERIOR`: el mock no recibe `documento_deuda_id`.
- Sin reversos, devoluciones ni disputas (W5).
- No se ejecutó CrewAI con un modelo real (Copilot sin autenticar); sí dry-run, MCP real y pruebas.
- Aprobación final del Product Owner pendiente (humana).
