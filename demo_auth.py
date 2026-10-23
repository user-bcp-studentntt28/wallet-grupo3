"""Usuarios de la demo: registro y login con clave de 6 dígitos.

El mock del grupo 3 no tiene autenticación; esta capa solo protege la pantalla de
ingreso de la demo. Se guarda un hash PBKDF2 con sal (nunca la clave ni el documento)
y los identificadores del mock. No es seguridad de producción: las rutas /api no
exigen sesión.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

PBKDF2_ROUNDS = 200_000
MAX_FAILURES = 5
LOCK_SECONDS = 60
DEFAULT_PATH = Path(__file__).resolve().parent / "evidence" / "demo_users.json"


def user_key(document: str) -> str:
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def alias_for(document: str) -> str:
    return f"{document[:5]}…{document[-3:]}" if len(document) > 8 else "TEST-…"


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    _, candidate = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, hash_hex)


class UserStore:
    def __init__(self, path: Path | None = DEFAULT_PATH, clock=time.monotonic) -> None:
        self._path = Path(path) if path else None
        self._clock = clock
        self._lock = threading.Lock()
        self._failures: dict[str, tuple[int, float]] = {}
        self._users: dict[str, dict[str, str]] = {}
        if self._path and self._path.is_file():
            try:
                self._users = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._users = {}

    def get(self, key: str) -> dict[str, str] | None:
        with self._lock:
            record = self._users.get(key)
            return dict(record) if record else None

    def add(self, key: str, record: dict[str, str]) -> None:
        with self._lock:
            self._users[key] = dict(record)
            self._save()

    def update_status(self, key: str, status: str) -> None:
        with self._lock:
            if key in self._users:
                self._users[key]["status"] = status
                self._save()

    def _save(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(".tmp")
        temp.write_text(json.dumps(self._users, indent=2), encoding="utf-8")
        os.replace(temp, self._path)

    def locked_seconds(self, key: str) -> int:
        with self._lock:
            count, until = self._failures.get(key, (0, 0.0))
            remaining = until - self._clock()
            return int(remaining) + 1 if count >= MAX_FAILURES and remaining > 0 else 0

    def register_failure(self, key: str) -> int:
        """Devuelve los intentos restantes antes del bloqueo temporal."""
        with self._lock:
            count, until = self._failures.get(key, (0, 0.0))
            if count >= MAX_FAILURES and until <= self._clock():
                count = 0
            count += 1
            self._failures[key] = (count, self._clock() + LOCK_SECONDS)
            return max(0, MAX_FAILURES - count)

    def clear_failures(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
