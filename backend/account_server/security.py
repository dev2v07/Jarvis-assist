from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .ids import new_secret


password_hasher = PasswordHasher()


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def validate_password(value: str) -> None:
    if len(value) < 12 or not any(c.islower() for c in value) or not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("password must be at least 12 characters and include upper, lower and digit")


def hash_password(value: str) -> str:
    validate_password(value)
    return password_hasher.hash(value)


def verify_password(encoded: str, value: str) -> bool:
    try:
        return password_hasher.verify(encoded, value)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def expires_after(seconds: int) -> datetime:
    return utcnow() + timedelta(seconds=seconds)


class RateLimiter:
    def __init__(self, limit: int = 20, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

