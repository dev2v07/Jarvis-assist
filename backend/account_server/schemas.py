from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16)


class LoginRequest(BaseModel):
    email: str
    password: str
    device_name: str = "Jarvis device"
    platform: str = "windows"
    client_version: str | None = None
    device_id: str | None = None


class GoogleExchangeRequest(BaseModel):
    id_token: str | None = Field(default=None, min_length=20)
    code: str | None = Field(default=None, min_length=10)
    code_verifier: str | None = Field(default=None, min_length=43, max_length=128)
    redirect_uri: str | None = None
    device_name: str = "Jarvis Windows"
    platform: str = "windows"
    client_version: str | None = None
    device_id: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=16)
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

