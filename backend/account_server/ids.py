from __future__ import annotations

import secrets
import time
import uuid


def new_uuid7() -> str:
    """Generate a UUIDv7-compatible lowercase string without a dependency."""
    timestamp_ms = int(time.time() * 1000)
    value = (timestamp_ms << 80) | secrets.randbits(76)
    value &= ~(0xF << 76)
    value |= 0x7 << 76
    value &= ~(0x3 << 62)
    value |= 0x2 << 62
    return str(uuid.UUID(int=value))


def new_secret() -> str:
    return secrets.token_urlsafe(48)

