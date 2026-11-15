from __future__ import annotations

import ctypes
import json
import os
import tempfile
from pathlib import Path


class CredentialStoreError(RuntimeError):
    pass


class CredentialStoreUnavailable(CredentialStoreError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


class WindowsDPAPICredentialStore:
    """Windows CurrentUser DPAPI adapter; never falls back to plaintext."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @staticmethod
    def _protect(raw: bytes) -> bytes:
        if os.name != "nt":
            raise CredentialStoreUnavailable("Windows DPAPI is unavailable on this platform")
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        source = ctypes.create_string_buffer(raw)
        source_blob = _DataBlob(len(raw), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
        target_blob = _DataBlob()
        if not crypt32.CryptProtectData(ctypes.byref(source_blob), None, None, None, None, 0, ctypes.byref(target_blob)):
            raise CredentialStoreError(f"CryptProtectData failed: {ctypes.get_last_error()}")
        try:
            return ctypes.string_at(target_blob.pbData, target_blob.cbData)
        finally:
            kernel32.LocalFree(target_blob.pbData)

    @staticmethod
    def _unprotect(raw: bytes) -> bytes:
        if os.name != "nt":
            raise CredentialStoreUnavailable("Windows DPAPI is unavailable on this platform")
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        source = ctypes.create_string_buffer(raw)
        source_blob = _DataBlob(len(raw), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
        target_blob = _DataBlob()
        if not crypt32.CryptUnprotectData(ctypes.byref(source_blob), None, None, None, None, 0, ctypes.byref(target_blob)):
            raise CredentialStoreError(f"CryptUnprotectData failed: {ctypes.get_last_error()}")
        try:
            return ctypes.string_at(target_blob.pbData, target_blob.cbData)
        finally:
            kernel32.LocalFree(target_blob.pbData)

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self._unprotect(self.path.read_bytes()).decode("utf-8"))
        except (OSError, ValueError, UnicodeError, CredentialStoreError) as exc:
            raise CredentialStoreError("protected credential data is unavailable or corrupt") from exc
        if not isinstance(payload, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in payload.items()):
            raise CredentialStoreError("protected credential data has invalid format")
        return payload

    def _write(self, payload: dict[str, str]) -> None:
        protected = self._protect(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="credentials-", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(protected)
                stream.flush()
                os.fsync(stream.fileno())
            Path(temporary).replace(self.path)
        finally:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass

    def read_access_token(self) -> str | None:
        return self._read().get("access_token")

    def read_refresh_token(self) -> str | None:
        return self._read().get("refresh_token")

    def write_tokens(self, access_token: str, refresh_token: str) -> None:
        if not access_token or not refresh_token:
            raise ValueError("both tokens are required")
        self._write({"access_token": str(access_token), "refresh_token": str(refresh_token)})

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise CredentialStoreError("protected credential data could not be removed") from exc
