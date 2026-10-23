# Runner CrewAI, MCP local y gates humanos

Cubre las tareas OpenSpec 7.1–7.5 de `wallet-demo-grupo3`.

## Skills por rol (HA-08)

`agents/skills/{product_owner,architect,ai_engineer,qa_security,presenter_timekeeper}.md`
definen fuentes, responsabilidades, entregable y límites de demo de cada rol.
`agents/common.py::build_agent` carga la skill del rol y la añade a la `backstory`
junto con las reglas compartidas. Si falta, no se puede leer o está vacía se lanza
`SkillError`: no hay instrucciones genéricas de respaldo.

## Runner secuencial

```powershell
# Sin modelo ni mock: agentes reales, salidas simuladas deterministas (nunca "ready")
python run_crew.py --dry-run

# Ejecución real (CrewAI + Copilot SDK, según .env: COPILOT_MODEL / COPILOT_USE_LOGGED_IN_USER)
python run_crew.py [--model gpt-6-luna] [--no-mcp]

# Versión de alcance vigente (hash de criterios, proposal y specs) para el registro humano
python run_crew.py --print-scope-version

# Reevaluar el gate final sobre una ejecución guardada (sin llamar al modelo)
python run_crew.py --finalize evidence\runs\<runId>

# Una llamada real y de solo lectura GET /scenarios por MCP stdio -> evidence\mcp_live_scenarios.json
python run_crew.py --mcp-smoke
```

Orden: guardrail de entrada (`guardrails/input_check.py`, antes de cualquier modelo y
antes de cada rol) → Product Owner (propuesta) → **gate humano de alcance** →
Arquitecto/a → AI Engineer → QA & Security → Presenter / Timekeeper → **gate humano final**.
Si un rol responde `BLOQUEADO` en su primera línea de contenido, los siguientes no corren.
Las herramientas de los agentes se validan contra `harness/policies/allowed_tools.json`
(lista `blocked`) y la lista de solo lectura del MCP. Las salidas quedan en
`evidence/runs/<runId>/` (ignorado por git) con `report.json`.

Códigos de salida: `0` = `READY` o `DRY_RUN_COMPLETE`; `2` = bloqueado/pendiente; `1` = error.
Estados: `BLOCKED_INPUT`, `BLOCKED_SCOPE`, `BLOCKED_ROLE`, `AWAITING_FINAL_APPROVAL`,
`FINAL_REJECTED`, `FINAL_APPROVAL_INVALID`, `READY`, `DRY_RUN_COMPLETE`.
`ready` solo es `true` con ejecución real, cuatro entregas y aprobación humana final válida.

## Registros de aprobación humana (los escribe una persona; el runner nunca los crea)

`evidence/scope_approval.json` (HA-02):

```json
{
  "scopeVersion": "wallet-demo-grupo3@<hash de --print-scope-version>",
  "decision": "APPROVED",
  "approver": "Nombre de la persona",
  "approverType": "HUMAN",
  "timestamp": "2026-10-23T15:00:00-05:00"
}
```

Bloquea todo trabajo posterior si falta, está `REJECTED`, es ilegible, el aprobador es un
agente/rol (`Product Owner`, `CrewAI`, …), el `timestamp` no es ISO con zona horaria o la
`scopeVersion` no coincide con la vigente (cualquier cambio en criterios, proposal o specs).

`evidence/final_approval.json` (HA-09), después de revisar `report.json` y las salidas:

```json
{
  "scopeVersion": "wallet-demo-grupo3@<hash>",
  "decision": "APPROVED",
  "approver": "Nombre del Product Owner",
  "approverType": "HUMAN",
  "timestamp": "2026-10-23T18:00:00-05:00",
  "evidenceRefs": ["evidence/runs/<runId>/report.json", "evidence/runs/<runId>/04_qa_security.md"],
  "unresolvedGaps": ["W3: pago de documento de deuda POSTERIOR (el mock no recibe documento_deuda_id)"],
  "reviewedDigest": "<evidenceDigest de report.json>"
}
```

`reviewedDigest` liga la decisión a las entregas revisadas; si se editan o corresponde a otra
ejecución, el resultado no es `ready`. Luego: `python run_crew.py --finalize evidence\runs\<runId>`.
Faltante o `REJECTED` ⇒ la demo **no** está lista; la salida de ningún agente cuenta como aprobación.

## MCP local de solo lectura (HA-05)

`mcp_group3_server.py` (stdio, FastMCP del paquete `mcp`, ya instalado con CrewAI) expone solo
las entradas `mcp_read_only` del `FEATURE_MAP`: `get_scenarios`, `get_wallet(resource_id)` y
`get_payment(resource_id)`. Cada llamada pasa por `check_mock_call`, valida el ID, usa la URL
fija `https://bcp-wallet-mock.yefri.workers.dev/groups/3` (con `User-Agent: WalletDemo/1.0`, sin
redirecciones) y filtra la respuesta con `check_mock_response`. Escrituras, `/control/reset`,
shell y URL arbitrarias se rechazan con su código `DEMO-TOOL-01/02/03`, `DEMO-IN-*`, `DEMO-OUT-01`;
un fallo del mock o del MCP se informa como fallo, nunca como éxito.
`agents/mcp_tools.py` descubre las herramientas por stdio y las envuelve como herramientas
CrewAI (solo Arquitecto/a y QA las reciben). `CALL_LOG` y `report.json` registran las llamadas.

## Pruebas

```powershell
python tools\verify.py
python -m unittest discover -s tests -p "test_hackaton*.py" -v
```
