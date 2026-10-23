"""Guardrails de la demo Wallet Perú, alineados con el patrón del repo.

Entrada (DEMO-IN), herramientas/rutas (DEMO-TOOL) y salida (DEMO-OUT), cada
regla con código. La tabla FEATURE_MAP es a la vez el mapa de funcionalidades:
cada operación del mock del grupo 3 está clasificada y enlazada a su criterio.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple

from guardrails.input_check import PII_PATTERNS, SECRET_PATTERNS

ALLOW = "ALLOW"
CONFIRM = "CONFIRM"
DENY = "DENY"

RESOURCE_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
MAX_DOCUMENT_LENGTH = 200


class GuardrailResult(NamedTuple):
    allowed: bool
    rule_code: str
    reason: str


@dataclass(frozen=True)
class Feature:
    method: str
    path: str
    policy: str
    functionality: str
    criteria: str
    task: str
    backend_route: str = "-"
    mcp_read_only: bool = False
    note: str = ""


# (método, ruta del mock) → clasificación, criterio y tarea OpenSpec.
FEATURE_MAP: tuple[Feature, ...] = (
    Feature("GET", "/health", ALLOW, "Salud del mock", "HA-05", "2.1", "/api/health"),
    Feature("GET", "/scenarios", ALLOW, "Escenarios disponibles", "HA-05, W1-03", "2.1",
            "/api/scenarios", mcp_read_only=True),
    Feature("GET", "/openapi.json", ALLOW, "Contrato OpenAPI", "HA-01", "1.2"),
    Feature("POST", "/kyc/verifications", ALLOW, "Registro KYC simulado", "W1-02, W1-03, W1-07",
            "3.1", "/api/kyc", note="Solo TEST-; sin PII ni secretos"),
    Feature("GET", "/kyc/verifications/{id}", ALLOW, "Consultar KYC", "W1-03, W1-04", "3.2"),
    Feature("POST", "/kyc/verifications/{id}/decision", CONFIRM, "Decisión humana de revisión",
            "W1-04", "3.2", note="Solo facilitador"),
    Feature("GET", "/wallets/{id}", ALLOW, "Estado y saldo de wallet", "W1-05, W2-02", "3.2",
            mcp_read_only=True),
    Feature("POST", "/qrs", ALLOW, "Generar QR de prueba", "W3-01", "4.1"),
    Feature("POST", "/qrs/resolve", ALLOW, "Resolver QR", "W2-01, W3-01, W3-06", "4.1"),
    Feature("POST", "/payments", CONFIRM, "Crear pago con Idempotency-Key",
            "W2-03, W2-04, W3-03, W4-01", "4.2", note="Confirmación explícita del pagador"),
    Feature("GET", "/payments", ALLOW, "Historial por wallet", "W2-08", "4.3"),
    Feature("GET", "/payments/{id}", ALLOW, "Consultar pago", "W2-06, W2-07, W3-04", "4.3",
            mcp_read_only=True),
    Feature("GET", "/payments/{id}/receipt", ALLOW, "Comprobante", "W2-08", "4.3"),
    Feature("GET", "/provider/payments/{id}", ALLOW, "Fuente del proveedor", "W5-02", "5.2"),
    Feature("POST", "/payments/{id}/resolve", CONFIRM, "Resolver pago incierto", "W5-02, W2-06",
            "5.2", note="Nunca crea un segundo pago"),
    Feature("POST", "/callbacks/payments", CONFIRM, "Evento duplicado de proveedor",
            "W4-04", "5.1", note="Control de prueba"),
    Feature("GET", "/control/events", ALLOW, "Eventos con contador de entrega", "W4-04", "5.1"),
    Feature("POST", "/control/events/{id}/deliver", CONFIRM, "Entregar o repetir evento",
            "W4-04", "5.1", note="Control de prueba"),
    Feature("POST", "/control/provider/{id}/complete", CONFIRM, "Finalizar proveedor pendiente",
            "W2-06", "4.3", note="Control de prueba"),
    Feature("GET", "/reversals/{id}", ALLOW, "Mostrar reverso ya existente", "W5-05", "5.3"),
    Feature("POST", "/payments/{id}/reversals", DENY, "Reverso de pago", "W5-05", "5.3",
            note="Fuera de alcance: W5 excluye reversos"),
    Feature("GET", "/support/cases", ALLOW, "Casos de soporte (solo lectura)", "W5-04", "5.3"),
    Feature("GET", "/ledger", ALLOW, "Asientos del mock", "W6-02", "6.1"),
    Feature("GET", "/settlements", ALLOW, "Reporte grupal", "W6-02, W6-05", "6.1"),
    Feature("GET", "/reconciliations/incidents", ALLOW, "Incidencias", "W6-03", "6.1"),
    Feature("POST", "/reconciliations", ALLOW, "Ejecutar conciliación", "W6-01", "6.1"),
    Feature("POST", "/control/settlements", CONFIRM, "Alterar reporte (AMOUNT/CLEAR)",
            "W6-06", "6.2", note="Confirmación humana del facilitador"),
    Feature("POST", "/control/reset", DENY, "Reiniciar datos del grupo", "HA-05, W6-06",
            "6.2", note="Nunca; borra datos compartidos"),
    Feature("GET", "/groups", DENY, "Listar grupos", "HA-05", "-",
            note="Fuera de alcance: datos de otros grupos"),
    Feature("GET", "/usage", DENY, "Uso acumulado", "HA-05", "-", note="Fuera de alcance"),
    Feature("GET", "/usage/all", DENY, "Uso de todos los grupos", "HA-05", "-",
            note="Fuera de alcance: datos de otros grupos"),
    Feature("GET", "/logs", DENY, "Registro de solicitudes", "HA-05", "-", note="Fuera de alcance"),
)


def _compile(path: str) -> re.Pattern[str]:
    escaped = re.escape(path).replace(re.escape("{id}"), r"([^/]+)")
    return re.compile(escaped + r"\Z")


_COMPILED = tuple((feature, _compile(feature.path)) for feature in FEATURE_MAP)


def _match(method: str, path: str) -> tuple[Feature, tuple[str, ...]] | None:
    for feature, pattern in _COMPILED:
        if feature.method == method.upper():
            found = pattern.fullmatch(path)
            if found:
                return feature, found.groups()
    return None


def classify(method: str, path: str) -> Feature | None:
    matched = _match(method, path)
    return matched[0] if matched else None


def check_mock_call(method: str, path: str, confirmed: bool = False) -> GuardrailResult:
    """Puerta de rutas: negar por defecto cualquier operación no mapeada."""
    matched = _match(method, path)
    if matched is None:
        return GuardrailResult(
            False, "DEMO-TOOL-01", "Operación no mapeada: se deniega por defecto."
        )
    feature, resource_ids = matched
    if feature.policy == DENY:
        return GuardrailResult(
            False, "DEMO-TOOL-02", f"Operación prohibida en la demo: {feature.functionality}."
        )

    if not all(RESOURCE_ID.fullmatch(resource_id) for resource_id in resource_ids):
        return GuardrailResult(False, "DEMO-IN-04", "Identificador de recurso inválido.")

    if feature.policy == CONFIRM and not confirmed:
        return GuardrailResult(
            False, "DEMO-TOOL-03", f"Requiere confirmación humana: {feature.functionality}."
        )
    return GuardrailResult(True, "", "OK")


def check_kyc_input(payload: object) -> GuardrailResult:
    """Entrada KYC: solo TEST-, sin PII ni secretos, campos acotados."""
    if not isinstance(payload, dict):
        return GuardrailResult(False, "DEMO-IN-01", "El cuerpo debe ser un objeto JSON.")
    if set(payload) - {"documentType", "document", "scenario"}:
        return GuardrailResult(False, "DEMO-IN-01", "La solicitud contiene campos no permitidos.")

    document = payload.get("document")
    if (
        payload.get("documentType") != "TEST"
        or not isinstance(document, str)
        or not document.startswith("TEST-")
        or len(document) > MAX_DOCUMENT_LENGTH
    ):
        return GuardrailResult(
            False, "DEMO-IN-02", "Usa documentType TEST y un documento ficticio con prefijo TEST-."
        )

    for pattern, label in (*SECRET_PATTERNS, *PII_PATTERNS):
        if re.search(pattern, document):
            return GuardrailResult(False, "DEMO-IN-03", f"El documento contiene datos sensibles ({label}).")
    return GuardrailResult(True, "", "OK")


def check_password(password: object) -> GuardrailResult:
    """Clave de 6 dígitos como en Yape; rechaza claves triviales."""
    if not isinstance(password, str) or not re.fullmatch(r"\d{6}", password):
        return GuardrailResult(False, "DEMO-IN-05", "La clave debe tener exactamente 6 dígitos.")
    if len(set(password)) == 1 or password in {"123456", "654321", "012345"}:
        return GuardrailResult(False, "DEMO-IN-05", "Elige una clave menos obvia (no repitas ni uses una secuencia).")
    return GuardrailResult(True, "", "OK")


def check_mock_response(body: bytes) -> GuardrailResult:
    """Salida: ninguna respuesta con secretos o PII llega al navegador."""
    text = body.decode("utf-8", errors="replace")
    for pattern, label in (*SECRET_PATTERNS, *PII_PATTERNS):
        if re.search(pattern, text):
            return GuardrailResult(
                False, "DEMO-OUT-01", f"Respuesta bloqueada: contiene {label}."
            )
    return GuardrailResult(True, "", "OK")


def public_feature_map() -> list[dict[str, object]]:
    return [
        {
            "method": f.method,
            "path": f.path,
            "policy": f.policy,
            "functionality": f.functionality,
            "criteria": f.criteria,
            "task": f.task,
            "backendRoute": f.backend_route,
            "mcpReadOnly": f.mcp_read_only,
            "note": f.note,
        }
        for f in FEATURE_MAP
    ]
