from __future__ import annotations

import secrets
import time
import uuid


def new_uuid7() -> str:
    """Create a UUIDv7 using only the Python standard library.

    Phase 1B uses this only for transient import/manifest IDs. Account and
    cloud entity IDs are still server-owned and are never fabricated locally.
    """

    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = timestamp_ms << 80
    value |= 0x7 << 76
    value |= random_a << 64
    value |= 0b10 << 62
    value |= random_b
    return str(uuid.UUID(int=value))


def is_uuid7(value: str) -> bool:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return parsed.version == 7 and parsed.variant == uuid.RFC_4122 and str(parsed) == str(value).lower()
