from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable

import certifi
import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


class GoogleIdentityError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedGoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    claims: dict[str, Any]


class GoogleIdentityValidator:
    def __init__(self, client_id: str, verifier: Callable[..., dict[str, Any]] | None = None) -> None:
        self.client_id = client_id
        if verifier:
            self._verifier = verifier
        else:
            session = requests.Session()
            session.verify = certifi.where()
            self._google_request = google_requests.Request(session=session)
            self._verifier = lambda raw, request, audience: id_token.verify_oauth2_token(
                raw,
                self._google_request,
                audience=audience,
                clock_skew_in_seconds=120,
            )

    def validate(self, raw_id_token: str) -> VerifiedGoogleIdentity:
        if not raw_id_token or not self.client_id:
            raise GoogleIdentityError("Google identity configuration is incomplete")
        try:
            claims = self._verifier(raw_id_token, google_requests.Request(), audience=self.client_id)
        except Exception as exc:
            detail = str(exc).replace("\n", " ").strip()[:180]
            raise GoogleIdentityError(f"Google ID token validation failed: {type(exc).__name__}{(': ' + detail) if detail else ''}") from exc
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise GoogleIdentityError("Google ID token issuer is invalid")
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if self.client_id not in audiences:
            raise GoogleIdentityError("Google ID token audience is invalid")
        expires_at = claims.get("exp")
        if not isinstance(expires_at, (int, float)) or expires_at <= time.time():
            raise GoogleIdentityError("Google ID token is expired")
        if not claims.get("sub"):
            raise GoogleIdentityError("Google ID token subject is missing")
        if claims.get("email_verified") is not True:
            raise GoogleIdentityError("Google email is not verified")
        email = str(claims.get("email") or "").strip().casefold()
        if "@" not in email:
            raise GoogleIdentityError("Google ID token email is invalid")
        return VerifiedGoogleIdentity(str(claims["sub"]), email, True, dict(claims))

