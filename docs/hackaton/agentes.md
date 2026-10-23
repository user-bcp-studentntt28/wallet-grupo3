# Primera entrega: cinco agentes CrewAI

Esta entrega define agentes y tareas reales de CrewAI directamente en
`agents/`. `main.py` ya recorre estos roles en orden con verificaciones
deterministas y levanta la demo (el laboratorio LangGraph anterior y sus tests
antiguos viven en `lab_main.py` y no son compatibles con los roles nuevos).
`tools/verify.py` verifica únicamente la entrega CrewAI.

## Archivos y entregables

| Rol | Implementación | Entregable |
|---|---|---|
| Product Owner | [product_owner.py](../../agents/product_owner.py) | Alcance y criterios pendientes de aprobación humana. |
| Arquitecto/a | [architect.py](../../agents/architect.py) | Pantallas, endpoints, estados y plan mínimo. |
| AI Engineer | [ai_engineer.py](../../agents/ai_engineer.py) | Incrementos de frontend y backend adaptador; en la configuración actual entrega propuestas porque no dispone de herramientas de filesystem/terminal. |
| QA & Security | [qa_security.py](../../agents/qa_security.py) | Matriz de pruebas, hallazgos y evidencia disponible. |
| Presenter / Timekeeper | [presenter_timekeeper.py](../../agents/presenter_timekeeper.py) | Guion de demo, tiempos estimados y pendientes. |

Cada módulo define un `INSTRUCTIONS` propio con el procedimiento y límites del
rol, además de `EXPECTED_OUTPUT` con la estructura que debe entregar. Expone
`create_agent(llm)` y `create_task(agent, context)`.
Arquitectura y QA aceptan además `tools`, una lista opcional de herramientas
CrewAI ya autorizadas por el runtime. No se incluyen herramientas por defecto.

La definición del agente establece rol, objetivo e instrucciones. La tarea
establece la solicitud de esa ejecución, las fuentes/contexto y el formato de
salida. `create_task` no ejecuta el agente: el runner futuro tendrá que construir
una `Crew` secuencial y ejecutar `kickoff` con los contextos reales. AI Engineer
es responsable de desarrollar web y backend adaptador, y funcionalidades propias
que cierren brechas aprobadas. El frontend llama al backend; el backend orquesta
el mock de grupo 3. Actualmente produce propuestas porque el runtime no le
proporciona herramientas para editar los workspaces ni ejecutar pruebas.

La [épica](../userstories/epic/peru-wallet-mvp.sp.md), las [seis historias](../userstories/user-stories/)
y los [criterios de aceptación](criterios-de-aceptacion.md) son las fuentes de
producto. La decisión humana debe identificar la versión aprobada; los criterios
del hackaton están pendientes hasta esa aprobación. El OpenAPI define capacidades
del mock, no requisitos de producto. Estas fuentes, la aprobación y el incremento
asignado deben pasarse en `context`; los agentes no leen archivos automáticamente.

## Preparación y validación local

En PowerShell, con el entorno Python del equipo:

```powershell
python -m pip install -r requirements-hackaton.txt
python tools\verify.py
```

En Git Bash, después de activar el entorno, los mismos comandos son:

```bash
python -m pip install -r requirements-hackaton.txt
python 'tools\verify.py'
```

Usa `python -c "import sys; print(sys.executable)"` para comprobar el entorno.
Instalar CrewAI en el Python global no lo instala en un `.venv` distinto.
El verificador muestra el intérprete efectivo y, si falta CrewAI, indica cómo
instalarlo con ese mismo Python; no instala dependencias automáticamente.

Las pruebas construyen los cinco agentes y sus tareas con un modelo de prueba
que falla si se intenta invocarlo. No llaman a modelos ni al mock real (el MCP
local se prueba con respuestas simuladas) y no requieren credenciales. No
demuestran ejecución multiagente con modelo ni operación web.
También se prueban el diagnóstico de dependencia faltante y la propagación de
fallos del verificador. Los tests antiguos no se ejecutan ni se presentan como
aprobados; requieren una migración separada.

Para usar las fábricas se debe suministrar un modelo configurado explícitamente,
compatible con CrewAI. Esta entrega no selecciona proveedor ni supone que la
sesión de Copilot lo autentique.

## Controles y pendientes de integración

- No se permite delegación autónoma ni ejecución de código mediante el agente.
- Las instrucciones limitan alcance, datos y resultados; no son por sí solas
  controles de permisos. El runtime debe restringir las herramientas y destinos.
- La tarea Product Owner usa `human_input=True` para revisión en CrewAI.
  Esa opción solicita feedback: **no implementa por sí sola una aprobación
  explícita, persistente y a prueba de rechazo**.
- Los roles cargan una skill especializada (`agents/skills/`); ver
  [runner.md](runner.md) para el runner secuencial (`run_crew.py`), los gates
  humanos inicial/final y el MCP local de solo lectura.
- Pendiente: web, pruebas funcionales W1–W6 y evidencias de una ejecución real
  con modelo (el entorno necesita credenciales de Copilot).
- La tarea Product Owner usa `human_input=True`: es feedback, no aprobación. La
  aprobación es el registro humano `evidence/scope_approval.json`.

Esta entrega permite revisar y repartir los cinco roles sin afirmar que el
hackaton completo o el gate de aprobación ya estén implementados.
