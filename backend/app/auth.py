"""Minimal single-instructor auth: one shared admin password is exchanged for a
signed, expiring bearer token. No user database."""

import base64
import hashlib
import hmac
import time

from fastapi import Header, HTTPException, status

from .config import settings

_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _sign(message: str) -> str:
    return hmac.new(
        settings.session_secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def create_token() -> str:
    message = f"admin:{int(time.time()) + _TTL_SECONDS}"
    raw = f"{message}:{_sign(message)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_token(token: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        message, sig = raw.rsplit(":", 1)
        if not hmac.compare_digest(sig, _sign(message)):
            return False
        _, exp = message.split(":")
        return int(exp) > time.time()
    except Exception:
        return False


def require_admin(authorization: str = Header(default="")) -> bool:
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return True
