"""Genera la presentación PDF de la demo Wallet Perú (grupo 3).

Historia: cómo construimos la solución con OpenSpec, cinco agentes CrewAI con skills,
un MCP local y gates humanos, y cómo resolvimos la wallet.

Uso: python tools/make_presentation.py [salida.pdf]
Las cifras salen de fuentes reales del repositorio (mapa de endpoints, evidencia de
la corrida, estado de OpenSpec, specs y una ejecución de las pruebas); si algo falla,
el script termina con error en lugar de imprimir números inventados.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_OUTPUT = ROOT / "docs" / "hackaton" / "presentacion-wallet-grupo3.pdf"
CHANGE_DIR = ROOT / "openspec" / "changes" / "wallet-demo-grupo3"

PAGE = (960, 540)
GREEN, DARK, MINT = HexColor("#087b5a"), HexColor("#075b44"), HexColor("#dff4eb")
INK, MUTED, LINE = HexColor("#132923"), HexColor("#64756f"), HexColor("#d4e3db")
WARM, WARM_INK = HexColor("#fff1d6"), HexColor("#7a4c05")
RED_BG, RED_INK = HexColor("#fde4df"), HexColor("#8f2d1f")
MARGIN = 56
CONTENT_W = PAGE[0] - 2 * MARGIN


def count_tests() -> int:
    total = 0
    commands = (
        [sys.executable, "-m", "unittest", "tests.test_demo_routes", "tests.test_demo_guardrails",
         "tests.test_wallet_demo_server", "tests.test_demo_auth", "tests.test_main_entrypoint"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_hackaton*.py"],
    )
    for command in commands:
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        output = run.stderr + run.stdout
        found = re.search(r"Ran (\d+) tests?", output)
        if run.returncode != 0 or not found:
            raise SystemExit(f"Las pruebas fallan; no se genera la presentación.\n{output[-600:]}")
        total += int(found.group(1))
    return total


def evidence_counts() -> dict[str, int]:
    text = (ROOT / "docs" / "hackaton" / "evidencia-demo.md").read_text(encoding="utf-8")
    counts = {"APROBADO": 0, "NO EJECUTADO": 0, "BLOQUEADO": 0, "FALLIDO": 0}
    for row in re.finditer(r"^\|\s*((?:W|IA)[\w-]*[\w()\s]*?)\s*\|\s*(APROBADO|NO EJECUTADO|BLOQUEADO|FALLIDO)\s*\|", text, re.M):
        counts[row.group(2)] += 1
    if not counts["APROBADO"]:
        raise SystemExit("No se pudo leer la evidencia de la corrida.")
    return counts


def feature_counts() -> tuple[int, int, int, int]:
    from demo_guardrails import ALLOW, CONFIRM, DENY, FEATURE_MAP

    by = lambda policy: sum(1 for f in FEATURE_MAP if f.policy == policy)  # noqa: E731
    return len(FEATURE_MAP), by(ALLOW), by(CONFIRM), by(DENY)


def openspec_stats() -> tuple[int, int, int, int]:
    tasks = (CHANGE_DIR / "tasks.md").read_text(encoding="utf-8")
    done = len(re.findall(r"^- \[x\]", tasks, re.M))
    total = done + len(re.findall(r"^- \[ \]", tasks, re.M))
    specs = sorted((CHANGE_DIR / "specs").glob("*/spec.md"))
    requirements = sum(len(re.findall(r"^### Requirement:", s.read_text(encoding="utf-8"), re.M)) for s in specs)
    return done, total, len(specs), requirements


class Deck:
    def __init__(self, path: Path) -> None:
        self.c = canvas.Canvas(str(path), pagesize=landscape(PAGE))
        self.c.setTitle("Perú Wallet - Agentes, skills, MCP y solución")
        self.c.setAuthor("Grupo 3")
        self.page = 0

    def slide(self, title: str, kicker: str = "") -> None:
        if self.page:
            self.c.showPage()
        self.page += 1
        c = self.c
        c.setFillColor(HexColor("#f2f5f4"))
        c.rect(0, 0, *PAGE, fill=1, stroke=0)
        c.setFillColor(GREEN)
        c.rect(0, PAGE[1] - 8, PAGE[0], 8, fill=1, stroke=0)
        if kicker:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(MARGIN, PAGE[1] - 50, kicker.upper())
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 28)
        c.drawString(MARGIN, PAGE[1] - 84, title)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 10)
        c.drawString(MARGIN, 24, "Perú Wallet · Grupo 3 · Hackatón")
        c.drawRightString(PAGE[0] - MARGIN, 24, str(self.page))

    def text(self, x, y, text, size=14, color=INK, bold=False, width=None, leading=None) -> float:
        c = self.c
        font = "Helvetica-Bold" if bold else "Helvetica"
        c.setFillColor(color)
        c.setFont(font, size)
        leading = leading or size * 1.3
        lines = []
        for paragraph in text.split("\n"):
            lines.extend(simpleSplit(paragraph, font, size, width) if width else [paragraph])
        for line in lines:
            c.drawString(x, y, line)
            y -= leading
        return y

    def bullets(self, x, y, items, width, size=15, gap=8) -> float:
        for item in items:
            self.c.setFillColor(GREEN)
            self.c.circle(x + 4, y + size * 0.32, 2.6, fill=1, stroke=0)
            y = self.text(x + 18, y, item, size, INK, width=width - 18) - gap
        return y

    def box(self, x, y, w, h, title, body="", fill=white, edge=LINE, title_color=DARK, size=11) -> None:
        c = self.c
        c.setFillColor(fill)
        c.setStrokeColor(edge)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, 10, fill=1, stroke=1)
        if not title:
            return
        cursor = self.text(x + 12, y + h - 22, title, 13, title_color, bold=True, width=w - 24)
        if body:
            self.text(x + 12, cursor - 2, body, size, INK, width=w - 24, leading=size * 1.32)

    def arrow(self, x1, y1, x2, y2) -> None:
        c = self.c
        c.setStrokeColor(GREEN)
        c.setFillColor(GREEN)
        c.setLineWidth(2)
        c.line(x1, y1, x2 - 8, y2)
        path = c.beginPath()
        path.moveTo(x2, y2)
        path.lineTo(x2 - 10, y2 + 5)
        path.lineTo(x2 - 10, y2 - 5)
        path.close()
        c.drawPath(path, fill=1, stroke=0)

    def table(self, x, y, widths, header, rows, size=10.5) -> float:
        c = self.c
        pad = 8
        leading = size * 1.3
        c.setFillColor(GREEN)
        c.roundRect(x, y - 24, sum(widths), 26, 6, fill=1, stroke=0)
        cx = x
        for width, label in zip(widths, header):
            self.text(cx + pad, y - 16, label, 11, white, bold=True)
            cx += width
        y -= 26
        for index, row in enumerate(rows):
            wrapped = [simpleSplit(cell, "Helvetica-Bold" if i == 0 else "Helvetica", size, widths[i] - 2 * pad)
                       for i, cell in enumerate(row)]
            height = max(len(w) for w in wrapped) * leading + 10
            c.setFillColor(white if index % 2 == 0 else HexColor("#eef5f1"))
            c.rect(x, y - height, sum(widths), height, fill=1, stroke=0)
            cx = x
            for i, (width, lines) in enumerate(zip(widths, wrapped)):
                self.text(cx + pad, y - 6 - size, "\n".join(lines), size, DARK if i == 0 else INK,
                          bold=i == 0, leading=leading)
                cx += width
            y -= height
        return y

    def save(self) -> None:
        self.c.showPage()
        self.c.save()


def build(path: Path) -> None:
    tests = count_tests()
    counts = evidence_counts()
    total_ops, allowed, confirm, denied = feature_counts()
    done, tasks, specs, requirements = openspec_stats()
    deck = Deck(path)

    # 1. Portada
    deck.slide("Perú Wallet", "Hackatón · Grupo 3")
    deck.text(MARGIN, 330, "Cómo la construimos con agentes, skills y MCP", 32, INK, bold=True)
    deck.text(MARGIN, 288, "y cómo resolvimos la wallet contra el mock del grupo 3", 22, GREEN)
    deck.text(MARGIN, 220, "OpenSpec · CrewAI (5 roles) · MCP local · guardrails · aprobación humana", 16, MUTED)
    deck.text(MARGIN, 190, "23 de octubre de 2026", 14, MUTED)
    deck.box(MARGIN, 80, 420, 64, "Cómo se ejecuta", "python main.py  ->  http://127.0.0.1:8000", fill=MINT, edge=MINT, size=14)

    # 2. Reto y estrategia
    deck.slide("El reto y nuestra estrategia", "Punto de partida")
    deck.box(MARGIN, 250, 410, 180, "El reto", "Una wallet tipo Yape: registro, pago QR, reintentos seguros, fallas, soporte y conciliación sobre un mock con 32 operaciones. CrewAI y MCP son obligatorios.", size=13)
    deck.box(494, 250, 410, 180, "Tres decisiones", "1. Especificar antes de construir (OpenSpec).\n2. Una persona aprueba; los agentes proponen.\n3. Nada es 'aprobado' sin evidencia observada.", fill=MINT, edge=GREEN, size=13)
    deck.box(MARGIN, 90, CONTENT_W, 130, "Regla de oro", "El mock del grupo 3 es la única autoridad financiera: ni los agentes ni la web inventan saldos, pagos o ledger. Lo que el mock no ofrece se declara como brecha, no se simula.", fill=WARM, edge=WARM, title_color=WARM_INK, size=13)

    # 3. OpenSpec
    deck.slide("Spec-driven con OpenSpec", "Cómo planificamos")
    steps = ["Propuesta", "Specs", "Diseño", "Tareas", "Implementación"]
    x = MARGIN
    for name in steps:
        deck.box(x, 340, 150, 60, name, "", fill=MINT if name == "Propuesta" else white, size=11)
        if name != steps[-1]:
            deck.arrow(x + 150, 370, x + 170, 370)
        x += 170
    deck.bullets(MARGIN, 300, [
        f"{specs} capacidades y {requirements} requisitos verificables, cada uno trazado a las historias W1-W6.",
        f"{done}/{tasks} tareas completadas; cada una con su evidencia de verificación.",
        "Los recortes de demo se marcan DEMO, POSTERIOR o BLOQUEADO; las historias originales no se editan.",
        "El alcance fue aprobado por una persona antes de implementar (tarea 1.1, en la conversación); el registro firmado para el runner sigue pendiente. Jira solo con autorización aparte.",
    ], CONTENT_W, size=14, gap=10)

    # 4. Equipo CrewAI
    deck.slide("El equipo de agentes CrewAI", "Cinco roles, un orden, entregables distintos")
    roles = [("1", "Product Owner", "Propuesta de alcance y trazabilidad W1-W6"),
             ("2", "Arquitecto/a", "Matriz de contratos, estados y MCP"),
             ("3", "AI Engineer", "Cambios por workspace y verificación"),
             ("4", "QA & Security", "Matriz por criterio y dictamen"),
             ("5", "Presenter / Timekeeper", "Guion, evidencia y limitaciones")]
    x = MARGIN
    for number, name, task in roles:
        deck.box(x, 300, 160, 110, f"{number}. {name}", task, size=11)
        if number != "5":
            deck.arrow(x + 160, 355, x + 176, 355)
        x += 176
    deck.bullets(MARGIN, 260, [
        "Secuencial: cada rol recibe las fuentes aprobadas y la entrega del anterior.",
        "Si un rol responde BLOQUEADO, los siguientes no corren: no se rellena con invenciones.",
        "Cada entregable tiene formato exacto y distingue hecho, propuesta y evidencia ejecutada.",
        "No usamos LangGraph: el flujo del hackatón es CrewAI; el laboratorio anterior quedó aparte (lab_main.py).",
    ], CONTENT_W, size=13, gap=8)

    # 5. Skills
    deck.slide("Skills especializadas por rol", "Una skill por agente, cargada de verdad")
    deck.table(MARGIN, 436, [150, 230, 250, 218], ["Rol", "Fuentes propias", "Entregable", "Límite clave"], [
        ("Product Owner", "Historias W1-W6, epic, criterios", "Alcance + trazabilidad + solicitud de aprobación", "No aprueba su propia propuesta"),
        ("Arquitecto/a", "OpenAPI del mock, mapa de guardrails", "Matriz de contratos y modelo de estados", "El diseño no crea saldo ni ledger"),
        ("AI Engineer", "Alcance aprobado y matriz", "Cambios por workspace + verificación", "Sin documento_deuda_id ni reversos"),
        ("QA & Security", "Criterios y evidencia observada", "Matriz con 4 etiquetas + dictamen", "Sin evidencia no hay APROBADO"),
        ("Presenter", "Evidencias, brechas, guion", "Guion, tiempos y limitaciones", "PENDING no es éxito"),
    ], size=10.5)
    deck.box(MARGIN, 66, CONTENT_W, 56, "", "")
    deck.text(MARGIN + 14, 100, "Mecanismo: agents/common.py carga la skill en la backstory del agente. Si falta, es ilegible o está vacía se lanza SkillError: no hay instrucciones genéricas de respaldo.", 11.5, INK, width=CONTENT_W - 28)

    # 6. Runner y gates
    deck.slide("Cómo corre el equipo", "Runner secuencial con dos gates humanos")
    pipeline = [("Guardrail\nde entrada", MINT), ("Product\nOwner", white), ("GATE\nalcance", WARM), ("Arquitecto/a", white),
                ("AI\nEngineer", white), ("QA &\nSecurity", white), ("Presenter", white), ("GATE\nfinal", WARM)]
    x = MARGIN
    for label, fill in pipeline:
        deck.box(x, 345, 96, 62, "", "", fill=fill, edge=GREEN if fill == WARM else LINE)
        deck.text(x + 8, 388, label, 10.5, WARM_INK if fill == WARM else DARK, bold=True, leading=13)
        if label != "GATE\nfinal":
            deck.arrow(x + 96, 376, x + 108, 376)
        x += 108
    deck.bullets(MARGIN, 300, [
        "El gate de alcance exige un registro firmado por una persona, ligado a la versión del alcance (hash de criterios, propuesta y specs); si algo cambia, hay que reaprobar.",
        "El gate final liga la decisión del Product Owner humano al digest de las entregas revisadas.",
        "Ningún agente puede aprobar: el runner solo lee los registros, nunca los crea.",
        "Dry-run: agentes reales con salidas simuladas; jamás devuelve 'ready'.",
    ], CONTENT_W, size=13, gap=8)
    deck.box(MARGIN, 66, CONTENT_W, 56, "Estado real", "Sin aprobación humana el runner se detiene en BLOQUEADO (código 2): es el comportamiento correcto, no un error.", fill=MINT, edge=MINT, size=11.5)

    # 7. MCP
    deck.slide("MCP local de solo lectura", "Cómo los agentes consultan el mock")
    deck.box(MARGIN, 330, 170, 90, "Agentes", "Arquitecto/a y QA reciben las herramientas", size=11)
    deck.box(270, 310, 190, 130, "Servidor MCP (stdio)", "get_scenarios\nget_wallet(id)\nget_payment(id)", fill=MINT, edge=GREEN, size=12)
    deck.box(504, 330, 170, 90, "Guardrails", "Ruta, ID y respuesta validados", size=11)
    deck.box(718, 330, 186, 90, "Mock grupo 3", "URL fija, sin redirecciones", size=11)
    deck.arrow(226, 375, 270, 375)
    deck.arrow(460, 375, 504, 375)
    deck.arrow(674, 375, 718, 375)
    deck.table(MARGIN, 280, [330, 130, 388], ["Intento del agente", "Código", "Resultado"], [
        ("Reset del grupo o reversos", "DEMO-TOOL-02", "Rechazado, nunca llega al mock"),
        ("Escritura / pago por MCP", "DEMO-TOOL-03", "Rechazado: requiere confirmación humana"),
        ("Herramienta o URL no listada", "DEMO-TOOL-01", "Denegado por defecto"),
        ("Respuesta con secreto o tarjeta", "DEMO-OUT-01", "Bloqueada; se informa como fallo"),
    ], size=10.5)
    deck.text(MARGIN, 96, "Evidencia: llamada real GET /scenarios por stdio (HTTP 200) y un agente CrewAI, con un LLM guionado, que consumió la respuesta real del MCP (no se probó con un modelo real). Un fallo del MCP se reporta como fallo, nunca como éxito.", 12, MUTED, width=CONTENT_W)

    # 8. Guardrails
    deck.slide("Guardrails: reglas, no opiniones", "Un guardrail valida, limita o bloquea y deja un código")
    deck.box(MARGIN, 250, 270, 160, "Entrada", "DEMO-IN-01..05\nSolo TEST-, campos permitidos, sin secretos ni tarjetas, IDs seguros y clave de 6 dígitos con hash y sal", size=11.5)
    deck.box(345, 250, 270, 160, "Rutas y herramientas", f"DEMO-TOOL-01..03\n{allowed} permitidas · {confirm} con confirmación humana · {denied} prohibidas. Lo no mapeado se deniega.", fill=MINT, edge=GREEN, size=11.5)
    deck.box(634, 250, 270, 160, "Salida", "DEMO-OUT-01\nNinguna respuesta con secretos o tarjetas llega al navegador ni al agente.", size=11.5)
    deck.box(MARGIN, 90, CONTENT_W, 130, "Un solo mapa para todo", f"El mismo FEATURE_MAP de {total_ops} operaciones gobierna el backend de la web, la lista permitida del MCP y la tabla visible en Operaciones. Una prueba falla si algún endpoint del contrato queda sin clasificar.", fill=WARM, edge=WARM, title_color=WARM_INK, size=12)

    # 9. Solución de la wallet
    deck.slide("Cómo resolvimos la wallet", "Navegador -> backend adaptador -> mock")
    deck.box(MARGIN, 290, 230, 130, "Navegador", "Login con clave\nPagos · Registro · Operaciones\nSolo llama al backend propio", size=12)
    deck.box(365, 270, 230, 170, "Backend adaptador (Python)", "Valida y traduce a las llamadas del mock\nGuardrails de entrada, rutas y salida\nTraza sin datos personales", fill=MINT, edge=GREEN, size=12)
    deck.box(674, 290, 230, 130, "Mock grupo 3", "Autoridad: wallets, pagos,\nledger, soporte, conciliación", size=12)
    deck.arrow(286, 355, 365, 355)
    deck.arrow(595, 355, 674, 355)
    deck.bullets(MARGIN, 230, [
        "Sin saldo ni estado de pago locales: el 'éxito' se muestra solo tras reconsultar al mock.",
        "Idempotency-Key por intento: reintento seguro, conflicto 409 y evento duplicado sin doble pago.",
        "Operaciones sensibles (pago, decisión KYC, alterar reporte) exigen confirmación explícita.",
        "Brecha honesta: el mock no recibe documento_deuda_id, así que el pago de una deuda concreta queda POSTERIOR.",
    ], CONTENT_W, size=13, gap=8)

    # 10. La wallet en uso
    deck.slide("La wallet en uso", "Lo que ve la persona")
    rows = [
        ("Registro / ingreso", "Usuario TEST- con clave de 6 dígitos; si ya existe, ingresa; KYC simulado y decisión humana si hay revisión manual."),
        ("Pagos", "Mi saldo, pagar a contacto o comercio varias veces, confirmación, 'Pago exitoso' solo tras consultar al mock, comprobante."),
        ("QR", "Generar y resolver QR (con imagen), pagar con su qrId; vista de comercio con filtros."),
        ("Fallas", "503, 504, QR vencido y rechazo con guía segura: reintentar solo cuando no se creó el pago."),
        ("Operaciones", "Soporte de solo lectura, liquidaciones, ledger, conciliación e incidencias; alteración AMOUNT/CLEAR con confirmación."),
    ]
    y = 420
    for name, desc in rows:
        deck.box(MARGIN, y - 52, 150, 46, "", "", fill=GREEN, edge=GREEN)
        deck.text(MARGIN + 12, y - 34, name, 13, white, bold=True, width=130)
        deck.text(226, y - 24, desc, 12, INK, width=678, leading=16)
        y -= 62

    # 11. main.py
    deck.slide("Los agentes también gobiernan el arranque", "python main.py")
    deck.table(MARGIN, 436, [210, 430, 208], ["Etapa (orden de los agentes)", "Qué verifica, sin llamar a un modelo", "Resultado típico"], [
        ("1. Product Owner", "Versión de alcance y aprobación humana inicial", "ADVERTENCIA si falta"),
        ("2. Arquitecto/a", f"{total_ops} operaciones clasificadas; reset y reversos prohibidos", "OK"),
        ("3. AI Engineer", "Módulos compilan, web completa, 5 skills presentes", "OK"),
        ("4. QA & Security", "Pruebas automatizadas de la demo", "OK / FALLO"),
        ("5. Presenter", "Puerto libre, URL y guion", "OK / FALLO"),
    ], size=11)
    deck.bullets(MARGIN, 190, [
        "Si ninguna etapa falla, levanta el servidor Python; con --strict exige la aprobación humana.",
        "--crew dry-run|real ejecuta además el runner CrewAI. Las etapas nunca inventan una aprobación.",
    ], CONTENT_W, size=13, gap=8)

    # 12. Lecciones
    deck.slide("Lo que nos enseñó probar con el mock real", "Hallazgos que el análisis no mostraba")
    deck.bullets(MARGIN, 410, [
        "El pago salía sin qrId: la resolución del QR no devuelve su ID. Lo derivamos del payload.",
        "El 503 real es PROVIDER_UNAVAILABLE (no PROVIDER_ERROR): la guía depende del estado HTTP.",
        "El 504 trae un status interno que no es el resultado: lo rotulamos como informado junto al error.",
        "El resumen de conciliación no separaba pagos con y sin diferencias (W6-04): lo completamos.",
        "El mock no tiene recarga: el saldo inicial es wallet-demo y se declara, no se simula.",
        "Un bug propio (clave de sessionStorage duplicada) rompió las llamadas: lo atrapó la prueba en navegador.",
    ], CONTENT_W, size=14, gap=12)

    # 13. Resultados y brechas
    deck.slide("Resultados y brechas", "Cifras de la corrida real")
    stats = [(f"{done}/{tasks}", "tareas OpenSpec completas"), (str(requirements), "requisitos verificables"),
             (str(tests), "pruebas automatizadas OK"), (str(counts["APROBADO"]), "criterios APROBADOS con evidencia")]
    x = MARGIN
    for value, label in stats:
        deck.box(x, 340, 200, 90, "", "", fill=MINT, edge=MINT)
        deck.text(x + 14, 395, value, 34, DARK, bold=True)
        deck.text(x + 14, 366, label, 11.5, INK, width=172)
        x += 216
    deck.box(MARGIN, 120, 410, 190, "Brechas declaradas", f"{counts['NO EJECUTADO']} criterios NO EJECUTADOS y {counts['BLOQUEADO']} BLOQUEADO (pago de una deuda concreta, POSTERIOR).\nCrewAI con modelo real no se ejecutó: Copilot sin autenticar; sí dry-run, MCP real y pruebas.\nSin reversos, devoluciones ni disputas.", fill=RED_BG, edge=RED_BG, title_color=RED_INK, size=11.5)
    deck.box(494, 120, 410, 190, "Requiere a una persona", "Aprobación de alcance (evidence/scope_approval.json).\nEnsayo cronometrado de la demo.\nAprobación final del Product Owner.\nEl mock es compartido: otros grupos pueden dejar incidencias abiertas.", fill=WARM, edge=WARM, title_color=WARM_INK, size=11.5)

    # 14. Cierre
    deck.slide("Demo en vivo", "Gracias")
    deck.bullets(MARGIN, 410, [
        "python main.py y abrir http://127.0.0.1:8000",
        "Registrarme con TEST-… y clave de 6 dígitos; luego Ingresar",
        "Pagar a un contacto y a un comercio y ver bajar el saldo",
        "Provocar un 503/504; mostrar el mapa de guardrails y el runner bloqueado sin aprobación",
    ], CONTENT_W, size=17, gap=14)
    deck.box(MARGIN, 90, CONTENT_W, 90, "Respaldo", "Si el mock no responde: se muestra el error tal cual, la evidencia de la corrida y los guardrails; no se simulan respuestas.", fill=MINT, edge=MINT, size=13)
    deck.save()


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    build(target)
    print(f"Presentación generada: {target}")
