"""Rutas del backend adaptador: validan la entrada y la convierten en una
llamada al mock del grupo 3. Toda llamada pasa después por demo_guardrails."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs

from demo_guardrails import RESOURCE_ID

MAX_CENTS = 100_000_000
IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9_-]{1,200}\Z")
KYC_SCENARIOS = {"APPROVED", "REJECTED", "MANUAL_REVIEW", "UNAVAILABLE"}
PAYMENT_SCENARIOS = {
    "APPROVED", "REJECTED", "PENDING", "DELAYED_APPROVAL",
    "TIMEOUT_AFTER_PROCESSING", "PROVIDER_ERROR",
}
RECIPIENTS = {"contact-demo", "merchant-demo"}


class RouteError(Exception):
    def __init__(self, message: str, rule_code: str = "DEMO-IN-01") -> None:
        super().__init__(message)
        self.message = message
        self.rule_code = rule_code


@dataclass(frozen=True)
class Plan:
    method: str
    mock_path: str
    payload: dict[str, object] | None = None
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    confirmed: bool = False
    event: str | None = None


def _is_int(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _only(body: dict[str, object], allowed: set[str]) -> None:
    if set(body) - allowed:
        raise RouteError("La solicitud contiene campos no permitidos.")


def _resource_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not RESOURCE_ID.fullmatch(value):
        raise RouteError(f"{label} no es un identificador válido.", "DEMO-IN-04")
    return value


def _confirmed(body: dict[str, object]) -> bool:
    return body.get("confirmed") is True


GET_ROUTES: tuple[tuple[re.Pattern[str], str, str | None], ...] = tuple(
    (re.compile(pattern + r"\Z"), template, event)
    for pattern, template, event in (
        (r"/api/kyc/([^/]+)", "/kyc/verifications/{0}", None),
        (r"/api/wallets/([^/]+)", "/wallets/{0}", None),
        (r"/api/payments", "/payments", None),
        (r"/api/payments/([^/]+)", "/payments/{0}", None),
        (r"/api/payments/([^/]+)/receipt", "/payments/{0}/receipt", None),
        (r"/api/provider/payments/([^/]+)", "/provider/payments/{0}", None),
        (r"/api/reversals/([^/]+)", "/reversals/{0}", "SUPPORT_REVERSAL_VIEWED"),
        (r"/api/support/cases", "/support/cases", "SUPPORT_CASES_VIEWED"),
        (r"/api/ledger", "/ledger", None),
        (r"/api/settlements", "/settlements", None),
        (r"/api/incidents", "/reconciliations/incidents", None),
        (r"/api/events", "/control/events", None),
    )
)


def plan_get(path: str, raw_query: str) -> Plan | None:
    for pattern, template, event in GET_ROUTES:
        found = pattern.fullmatch(path)
        if found:
            query: dict[str, str] = {}
            if path == "/api/payments":
                wallet = parse_qs(raw_query).get("walletId", ["wallet-demo"])[0]
                query["walletId"] = _resource_id(wallet, "walletId")
            return Plan("GET", template.format(*found.groups()), query=query, event=event)
    return None


def plan_post(path: str, body: dict[str, object]) -> Plan | None:
    confirmed = _confirmed(body)

    if path == "/api/qrs":
        _only(body, {"amountCents", "expiresInSeconds"})
        payload: dict[str, object] = {"merchantId": "merchant-demo"}
        amount = body.get("amountCents")
        if amount is not None:
            if not _is_int(amount, 1, MAX_CENTS):
                raise RouteError("amountCents debe ser un entero positivo en céntimos.")
            payload["amountCents"] = amount
        ttl = body.get("expiresInSeconds")
        if ttl is not None:
            if not _is_int(ttl, 0, 86_400):
                raise RouteError("expiresInSeconds debe estar entre 0 y 86400.")
            payload["expiresInSeconds"] = ttl
        return Plan("POST", "/qrs", payload, event="QR_CREATED")

    if path == "/api/qrs/resolve":
        _only(body, {"payload"})
        qr_text = body.get("payload")
        if not isinstance(qr_text, str) or not qr_text.startswith("qrmock:") or len(qr_text) > 200:
            raise RouteError("El payload debe ser un texto qrmock: creado por el mock.")
        return Plan("POST", "/qrs/resolve", {"payload": qr_text}, event="QR_RESOLVED")

    if path == "/api/payments":
        _only(body, {"walletId", "recipient", "amountCents", "qrId", "scenario",
                     "idempotencyKey", "confirmed"})
        wallet = _resource_id(body.get("walletId"), "walletId")
        if body.get("recipient") not in RECIPIENTS:
            raise RouteError("recipient debe ser contact-demo o merchant-demo.")
        if not _is_int(body.get("amountCents"), 1, MAX_CENTS):
            raise RouteError("amountCents debe ser un entero positivo en céntimos.")
        key = body.get("idempotencyKey")
        if not isinstance(key, str) or not IDEMPOTENCY_KEY.fullmatch(key):
            raise RouteError("idempotencyKey es obligatoria (1-200 caracteres seguros).")
        payload = {
            "walletId": wallet,
            "recipient": body["recipient"],
            "amountCents": body["amountCents"],
            "currency": "PEN",
        }
        if body.get("qrId") is not None:
            payload["qrId"] = _resource_id(body["qrId"], "qrId")
        scenario = body.get("scenario")
        if scenario is not None:
            if scenario not in PAYMENT_SCENARIOS:
                raise RouteError("scenario de pago no permitido.")
            payload["scenario"] = scenario
        return Plan("POST", "/payments", payload, {"Idempotency-Key": key},
                    confirmed=confirmed, event="PAYMENT_REQUESTED")

    if path == "/api/reconciliations":
        _only(body, set())
        return Plan("POST", "/reconciliations", {}, event="RECONCILIATION_RUN")

    if path == "/api/callbacks":
        _only(body, {"eventId", "confirmed"})
        event_id = _resource_id(body.get("eventId"), "eventId")
        return Plan("POST", "/callbacks/payments", {"eventId": event_id},
                    confirmed=confirmed, event="EVENT_DELIVERED")

    if path == "/api/control/settlements":
        _only(body, {"paymentId", "mode", "amountCents", "confirmed"})
        payment = _resource_id(body.get("paymentId"), "paymentId")
        mode = body.get("mode")
        if mode not in {"AMOUNT", "CLEAR"}:
            raise RouteError("En la demo solo se permiten los modos AMOUNT y CLEAR.")
        payload = {"paymentId": payment, "mode": mode}
        if mode == "AMOUNT":
            if not _is_int(body.get("amountCents"), 1, MAX_CENTS):
                raise RouteError("AMOUNT exige amountCents entero positivo.")
            payload["amountCents"] = body["amountCents"]
        return Plan("POST", "/control/settlements", payload,
                    confirmed=confirmed, event="SETTLEMENT_ALTERED")

    decision = re.fullmatch(r"/api/kyc/([^/]+)/decision", path)
    if decision:
        _only(body, {"decision", "confirmed"})
        if body.get("decision") not in {"ACTIVE", "REJECTED"}:
            raise RouteError("decision debe ser ACTIVE o REJECTED.")
        return Plan("POST", f"/kyc/verifications/{decision.group(1)}/decision",
                    {"decision": body["decision"]}, confirmed=confirmed, event="KYC_DECISION")

    resolve = re.fullmatch(r"/api/payments/([^/]+)/resolve", path)
    if resolve:
        _only(body, {"confirmed"})
        return Plan("POST", f"/payments/{resolve.group(1)}/resolve", {},
                    confirmed=confirmed, event="PAYMENT_RESOLVED")

    deliver = re.fullmatch(r"/api/control/events/([^/]+)/deliver", path)
    if deliver:
        _only(body, {"confirmed"})
        return Plan("POST", f"/control/events/{deliver.group(1)}/deliver", {},
                    confirmed=confirmed, event="EVENT_DELIVERED")

    complete = re.fullmatch(r"/api/control/provider/([^/]+)/complete", path)
    if complete:
        _only(body, {"status", "confirmed"})
        status = body.get("status", "SUCCEEDED")
        if status not in {"SUCCEEDED", "REJECTED"}:
            raise RouteError("status debe ser SUCCEEDED o REJECTED.")
        return Plan("POST", f"/control/provider/{complete.group(1)}/complete",
                    {"status": status}, confirmed=confirmed, event="PROVIDER_COMPLETED")

    return None
