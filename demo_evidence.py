from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime


_SAFE_EVENT_TYPE = re.compile(r"[A-Z][A-Z0-9_]{0,47}\Z")
_MAX_REFERENCE_LENGTH = 160


class DemoEvidenceStore:
    def __init__(self) -> None:
        self._events: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def record(
        self,
        event_type: str,
        *,
        wallet_id: str | None = None,
        qr_id: str | None = None,
        payment_id: str | None = None,
    ) -> dict[str, str]:
        if not _SAFE_EVENT_TYPE.fullmatch(event_type):
            raise ValueError("event_type must be a fixed uppercase label")

        event = {
            "eventType": event_type,
            "correlationId": uuid.uuid4().hex,
            "capturedAtLocal": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        }
        for key, value in (
            ("walletId", wallet_id),
            ("qrId", qr_id),
            ("paymentId", payment_id),
        ):
            if value is not None:
                event[key] = self._validate_reference(value)

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
