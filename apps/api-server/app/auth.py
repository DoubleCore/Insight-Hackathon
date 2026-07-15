from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


USER_COOKIE_NAME = "qa_user_session"
ADMIN_COOKIE_NAME = "qa_admin_session"
USER_COOKIE_MAX_AGE = 60 * 60 * 24 * 30
ADMIN_COOKIE_MAX_AGE = 60 * 60 * 8


def _base64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class CookieSigner:
    def __init__(self, secret: str):
        if not secret:
            raise ValueError("会话密钥不能为空")
        self._secret = secret.encode("utf-8")

    def sign(
        self, subject: str, purpose: str, *, max_age: int = USER_COOKIE_MAX_AGE
    ) -> str:
        payload: dict[str, Any] = {
            "sub": subject,
            "purpose": purpose,
            "expires": int(time.time()) + max_age,
        }
        encoded = _base64_encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        signature = hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
        return f"{encoded}.{_base64_encode(signature)}"

    def verify(self, token: str | None, purpose: str) -> str | None:
        if not token:
            return None
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = hmac.new(
                self._secret, encoded.encode("ascii"), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(_base64_decode(supplied_signature), expected_signature):
                return None
            payload = json.loads(_base64_decode(encoded))
            if payload.get("purpose") != purpose or payload.get("expires", 0) < time.time():
                return None
            subject = payload.get("sub")
            return subject if isinstance(subject, str) and subject else None
        except (ValueError, TypeError, json.JSONDecodeError):
            return None
