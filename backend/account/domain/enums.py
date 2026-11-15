from __future__ import annotations

from enum import Enum


class AccountMode(str, Enum):
    LOCAL_ONLY = "local_only"
    ACCOUNT = "account"


class AccountLifecycleState(str, Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    CONNECTING = "CONNECTING"
    AUTHENTICATED_DEVICE = "AUTHENTICATED_DEVICE"
    ACCOUNT_SYNCING = "ACCOUNT_SYNCING"
    ACCOUNT_ONLINE = "ACCOUNT_ONLINE"
    OFFLINE_ACCOUNT = "OFFLINE_ACCOUNT"
    AUTH_REQUIRED = "AUTH_REQUIRED"


class ConnectionState(str, Enum):
    LOCAL = "local"
    CONNECTING = "connecting"
    ONLINE = "online"
    OFFLINE = "offline"


class SessionState(str, Enum):
    LOCAL = "local"
    AUTHENTICATED = "authenticated"
    REQUIRED = "required"


class SyncState(str, Enum):
    NOT_CONFIGURED = "not_configured"
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"


class DataClass(str, Enum):
    CLOUD_SYNCED = "cloud_synced"
    DEVICE_ONLY = "device_only"
    EXCLUDED = "excluded"


class EntityType(str, Enum):
    CONVERSATION = "conversation"
    MESSAGE = "message"
    ATTACHMENT = "attachment"
    REACTION = "reaction"
    PIN = "pin"
    REQUEST = "request"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"


class InventoryItemStatus(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    CORRUPT = "corrupt"
    ORPHAN = "orphan"
    UNSUPPORTED = "unsupported"
