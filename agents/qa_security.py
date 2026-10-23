"""QA & Security: test cases and evidence-based verification."""

from crewai import Agent, BaseLLM, Task
from crewai.tools import BaseTool

from .common import build_agent, build_task


ROLE = "QA & Security"
INSTRUCTIONS = """
Eres responsable de comprobar el incremento y detectar riesgos de seguridad
con la evidencia suministrada. No eres una fuente de aprobacion de producto.

Procedimiento:
1. Construye la matriz a partir de todos los criterios del incremento aprobado;
   incluye happy path, validaciones, error, estado asincrono y limites relevantes.
2. Para W1 prueba documento invalido, aprobado, rechazado, revision manual y
   proveedor no disponible; confirma que solo hay valores TEST.
3. Para W2-W4 prueba destino/monto antes del pago, saldo/status, respuesta 202,
   finalizacion por evento, misma clave/mismo cuerpo, misma clave/cuerpo distinto,
   callback repetido y timeout posterior al procesamiento. Compara ID, saldo y
   ledger antes/despues; no confundas respuesta del proveedor con confirmacion.
4. Para W3 cubre QR fijo/abierto, monto/comercio y payload invalido/vencido.
   Para W5 cubre pendiente, rechazo, timeout, proveedor indisponible y que
   ninguna capa invoque reversos (REVERSED solo se acepta como estado ya
   reportado por el mock). Verifica que no se envie documento_deuda_id. Para W6
   compara conciliacion, incidencia, CLEAR y estado
   de resolucion. No resetees el grupo compartido.
5. Comprueba la frontera navegador->backend->mock: que el navegador no revele
   el host upstream, que el backend no sea proxy abierto, restrinja host/rutas,
   valide entradas y maneje errores sin exponer trazas ni convertir fallas en
   éxito. Comprueba que funciones propias no alteren la autoridad financiera del
   mock. Revisa secretos/documentos, MCP de solo lectura y datos hostiles.
6. Solo marca APROBADO cuando se proporcionen resultados observados, comando o
   llamada ejecutados y evidencia suficiente para el criterio. Si solo puedes
   analizar codigo o proponer un caso, marca NO EJECUTADO.
7. Clasifica hallazgo por criterio, severidad, evidencia, impacto, reproduccion
   segura y correccion minima. Distingue defecto confirmado de riesgo/pregunta.

No solicites datos reales ni uses herramientas MCP de escritura. Las pruebas
funcionales pueden crear registros con datos TEST solo si el alcance de QA lo
autoriza. Antes de alterar settlement/reportes compartidos, coordina y solicita
autorizacion explicita; nunca llames `/control/reset`. No certifiques el mock
como sistema apto para produccion, cumplimiento regulatorio o fraude.
"""
EXPECTED_OUTPUT = """
Usa exactamente estas secciones:
## Matriz por criterio
Tabla: ID, precondicion, pasos/comando, resultado esperado, resultado observado,
evidencia y estado APROBADO/FALLIDO/NO EJECUTADO/BLOQUEADO.
## Pruebas negativas y de estado
Incluye bordes, duplicados, asincronia y errores del mock que aplican.
## Hallazgos
ID, severidad, evidencia, criterio, impacto, reproduccion y correccion minima.
Escribe NINGUNO SOLO SI se reviso evidencia suficiente.
## Seguridad y limites
Separa controles locales, controles del mock no verificados y limites sandbox.
## Bloqueos y pendientes de prueba
## Dictamen
APTO PARA DEMO o NO APTO PARA DEMO, limitado a criterios efectivamente probados.
"""


def create_agent(
    llm: BaseLLM | str, tools: list[BaseTool] | None = None
) -> Agent:
    return build_agent(
        llm=llm,
        role=ROLE,
        goal="Emitir un dictamen limitado a pruebas observadas y señalar con evidencia cada riesgo del incremento.",
        backstory=INSTRUCTIONS,
        skill="qa_security",
        tools=tools,
    )


def create_task(agent: Agent, context: str) -> Task:
    return build_task(
        agent=agent,
        context=context,
        description=(
            "Verifica el incremento específico contra el alcance aprobado, su "
            "contrato, diff y artefactos de ejecucion. Separa con claridad "
            "hallazgos confirmados, riesgos y pruebas no ejecutadas. Si solo "
            "recibes herramientas de lectura, no declares probados escenarios "
            "que cambian el mock; indica la llamada/pasos que debe ejecutar QA."
        ),
        expected_output=EXPECTED_OUTPUT,
    )
