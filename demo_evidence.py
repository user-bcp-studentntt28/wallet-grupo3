from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime


_SAFE_EVENT_TYPE = re.compile(r"[A-Z][A-Z0-9_]{0,47}\Z")
_SAFE_RULE_CODE = re.compile(r"DEMO-(?:IN|TOOL|OUT)-\d{2}\Z")
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,200}\Z")
_ATTEMPTS = {"ORIGINAL", "RETRY"}
_MAX_REFERENCE_LENGTH = 160


class DemoEvidenceStore:
    def __init__(self) -> None:
        self._events: list[dict[str, str]] = []
        self._once: set[tuple[str, str]] = set()
        self._keys: set[str] = set()
        self._lock = threading.Lock()

    def note_attempt(self, idempotency_key: str) -> str:
        """Distingue el intento original de un reintento con la misma clave."""
        with self._lock:
            attempt = "RETRY" if idempotency_key in self._keys else "ORIGINAL"
            self._keys.add(idempotency_key)
        return attempt

    def record_once(self, event_type: str, once_key: str, **references: object) -> dict[str, str] | None:
        with self._lock:
            marker = (event_type, once_key)
            if marker in self._once:
                return None
            self._once.add(marker)
        return self.record(event_type, **references)

    def record(
        self,
        event_type: str,
        *,
        wallet_id: str | None = None,
        qr_id: str | None = None,
        payment_id: str | None = None,
        rule_code: str | None = None,
        event_id: str | None = None,
        idempotency_key: str | None = None,
        session_id: str | None = None,
        attempt: str | None = None,
        http_status: int | None = None,
    ) -> dict[str, str]:
        if not _SAFE_EVENT_TYPE.fullmatch(event_type):
            raise ValueError("event_type must be a fixed uppercase label")
        if rule_code is not None and not _SAFE_RULE_CODE.fullmatch(rule_code):
            raise ValueError("rule_code must be a guardrail rule label")
        if attempt is not None and attempt not in _ATTEMPTS:
            raise ValueError("attempt must be ORIGINAL or RETRY")
        if http_status is not None and not (
            isinstance(http_status, int) and not isinstance(http_status, bool) and 100 <= http_status <= 599
        ):
            raise ValueError("http_status must be an HTTP status code")

        event = {
            "eventType": event_type,
            "correlationId": uuid.uuid4().hex,
            "capturedAtLocal": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        }
        if rule_code is not None:
            event["ruleCode"] = rule_code
        if attempt is not None:
            event["attempt"] = attempt
        if http_status is not None:
            event["httpStatus"] = str(http_status)
        for key, value in (
            ("walletId", wallet_id),
            ("qrId", qr_id),
            ("paymentId", payment_id),
        ):
            if value is not None:
                event[key] = self._validate_reference(value)
        for key, value in (
            ("eventId", event_id),
            ("idempotencyKey", idempotency_key),
            ("sessionId", session_id),
        ):
            if value is not None:
                if not _SAFE_ID.fullmatch(value):
                    raise ValueError(f"{key} must be a safe identifier")
                event[key] = value

        with self._lock:
            self._events.append(event)
        return dict(event)

    def export(self) -> dict[str, object]:
        with self._lock:
            events = [dict(event) for event in self._events]
        return {"scope": "non-financial-demo-evidence", "events": events}

    @staticmethod
    def _validate_reference(value: str) -> str:
        if (
            not value
            or len(value) > _MAX_REFERENCE_LENGTH
            or any(ord(character) < 32 for character in value)
        ):
            raise ValueError("resource references must be non-empty printable IDs")
        return value
