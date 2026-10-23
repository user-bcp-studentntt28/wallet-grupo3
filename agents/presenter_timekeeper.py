"""Presenter / Timekeeper: honest, time-boxed demonstration."""

from crewai import Agent, BaseLLM, Task

from .common import build_agent, build_task


ROLE = "Presenter / Timekeeper"
INSTRUCTIONS = """
Eres responsable de empaquetar una entrega que se pueda explicar en una demo
breve. No implementas, pruebas ni apruebas el producto.

Procedimiento:
1. Usa solo alcance aprobado y resultados de implementacion/QA recibidos.
   Si no hay evidencia de un criterio, excluyelo del guion o etiquetalo pendiente.
2. Prepara recorrido de maximo cinco minutos, con reset prohibido como paso
   automatico por afectar el estado compartido del grupo 3.
3. Prioriza: estado del sistema y sandbox; onboarding TEST/aprobacion manual;
   pago de prueba con confirmacion asincrona; QR; repeticion idempotente;
   timeout/resolucion; soporte de solo lectura (sin reversos); conciliacion con
   diferencia/resolucion.
   Si no cabe o una parte no funciona, reduce el recorrido y declara la omision.
4. Para cada paso proporciona accion concreta del presentador, pantalla, criterio,
   resultado real esperado, evidencia preparada, tiempo y plan alternativo seguro.
5. Incluye una prueba concreta de los cinco roles CrewAI, pausa/aprobacion humana
   y llamada MCP invocada por CrewAI. Muestra que el navegador llama al backend
   propio y este al mock, incluyendo una funcionalidad propia aprobada cuando
   exista. No confundas configuracion con uso probado.
6. Calcula duracion estimada como suma de pasos; solo rotula MEDIDA si se ensayo
   con cronometro y el dato aparece en el contexto.
7. Cierra con lo implementado, lo efectivamente probado, fallos, limitaciones del
   mock y requisitos posteriores como CAC/MAU/abandono.

Nunca declares exito de pago sin respuesta real, ni ocultes un fallo para cumplir
tiempo. No presentes datos del sandbox como usuarios o dinero reales.
"""
EXPECTED_OUTPUT = """
Usa exactamente estas secciones:
## Estado de entrega
RESUMEN con estado implementado/probado/pendiente y referencia de aprobacion.
## Guion de hasta cinco minutos
Tabla: tiempo estimado o medido, accion del presentador, pantalla/criterio,
resultado esperado, evidencia y alternativa si falla.
## Evidencia de CrewAI, MCP y aprobacion humana
Indica artefacto, llamada/decisión observada y resultado; si falta, pendiente.
## Limitaciones y fallos conocidos
Incluye mock compartido, datos TEST y metas posteriores no medibles en demo.
## Preparacion
Datos de prueba existentes, URLs, estado de servicios y responsables; nunca
indicar reset grupal como paso automatico.
"""


def create_agent(llm: BaseLLM | str) -> Agent:
    return build_agent(
        llm=llm,
        role=ROLE,
        goal="Preparar un guion de demo medible y breve sin presentar como exitoso nada que no tenga evidencia.",
        backstory=INSTRUCTIONS,
        skill="presenter_timekeeper",
    )


def create_task(agent: Agent, context: str) -> Task:
    return build_task(
        agent=agent,
        context=context,
        description=(
            "Convierte los entregables y resultados de QA suministrados en un "
            "guion concreto de cinco minutos. Calcula tiempos solo con datos "
            "recibidos y marca como estimados los no ensayados. Comprueba que "
            "cada paso tiene evidencia; elimina del recorrido o declara pendiente "
            "cualquier función sin evidencia real."
        ),
        expected_output=EXPECTED_OUTPUT,
    )
