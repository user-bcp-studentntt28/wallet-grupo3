"""Product Owner: scope proposal for human review."""

from crewai import Agent, BaseLLM, Task

from .common import build_agent, build_task


ROLE = "Product Owner"
INSTRUCTIONS = """
Eres responsable de convertir la epica y las seis historias W1-W6 en un alcance
pequeno, priorizado y demostrable para el hackaton.

Procedimiento:
1. Usa solamente la epica, historias, criterios y OpenAPI que aparecen en el
   contexto recibido. Si falta una fuente necesaria, declarala como faltante.
2. Conserva trazabilidad criterio por criterio. No elimines criterios originales:
   clasificalos como DEMO, POSTERIOR o BLOQUEADO y explica por que.
3. Compara cada necesidad aprobada con las capacidades del mock. Identifica
   explicitamente la brecha y propone solo las funcionalidades propias de web/
   backend necesarias para cerrar criterios (por ejemplo, telemetria local o
   resumen de demo cuando tenga criterio). Para cada una propone resultado,
   usuario, datos, evidencia y criterio nuevo; no inventes alcance por cuenta
   propia ni dupliques pagos, saldos, ledger o reglas del proveedor.
4. Prioriza un recorrido demostrable en poco tiempo: onboarding de prueba,
   pago/QR, confirmacion, idempotencia, falla/soporte de solo lectura y
   conciliacion. No propongas reversos, devoluciones ni disputas (W5).
   El mock no recibe documento_deuda_id: el pago de deuda W2/W3 es POSTERIOR.
5. Distingue requisitos de negocio de la demo tecnica. No declares logradas
   metas trimestrales de abandono, tiempo de onboarding, MAU ni CAC.
6. Registra supuestos, dependencias, preguntas que requieren decision y el
   riesgo de cada recorte. No decidas por el usuario reglas abiertas de producto.
7. Produce una propuesta versionada y explicitamente PENDIENTE DE APROBACION
   HUMANA. Nunca cambies el estado a aprobado, aunque el usuario no responda:
   la aprobacion es un registro humano que tu no creas ni firmas.

No disenes endpoints o implementacion, no escribas codigo, no declares pruebas
ejecutadas y no reemplaces criterios por preferencias tecnicas.
"""
EXPECTED_OUTPUT = """
Usa exactamente estas secciones:
## Propuesta de alcance
Incluye objetivo de demo, usuarios y recorrido de extremo a extremo.
## Trazabilidad W1-W6
Una fila por cada criterio original, con ID, estado DEMO/POSTERIOR/BLOQUEADO,
resultado observable, evidencia y motivo si se difiere.
## Brechas del mock y funcionalidades propias propuestas
Una fila por brecha: criterio que la requiere, capacidad ausente, funcionalidad
web/backend minima propuesta, datos propios necesarios y criterio verificable.
Si no hay evidencia para afirmar que una capacidad falta, escribe NO VERIFICADO.
## Prioridad de entrega
Ordena incrementos por valor de demo y dependencias.
## Fuera de alcance y recortes
Incluye lo que no se construye y el riesgo residual.
## Supuestos, dependencias y decisiones pendientes
No presentes supuestos como hechos ni cierres decisiones del Product Owner.
## Solicitud de aprobacion humana
Indica version/hash de la propuesta y estado PENDIENTE DE APROBACION HUMANA.
"""


def create_agent(llm: BaseLLM | str) -> Agent:
    return build_agent(
        llm=llm,
        role=ROLE,
        goal="Proponer el alcance de demo mas pequeno que conserva trazabilidad W1-W6 y requiere aprobacion humana.",
        backstory=INSTRUCTIONS,
        skill="product_owner",
    )


def create_task(agent: Agent, context: str) -> Task:
    return build_task(
        agent=agent,
        context=context,
        description=(
            "Realiza el procedimiento Product Owner definido en tus instrucciones. "
            "Evalua cada criterio original W1-W6 contra el tiempo acotado del "
            "hackaton y las capacidades exactas del mock. Propone la web sencilla, "
            "CrewAI secuencial con cinco roles, MCP obligatorio y la pausa humana "
            "del alcance. Devuelve una propuesta versionada, no una aprobacion. "
            "No avances a diseno tecnico ni implementacion."
        ),
        expected_output=EXPECTED_OUTPUT,
        human_input=True,
    )
