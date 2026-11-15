from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

from account_server.app import create_app
from account_server.config import Settings
from account_server.email_provider import EmailProvider
from account_server.google_identity import GoogleIdentityError, GoogleIdentityValidator
from account_server.database import build_session_factory, dispose_session_factory
from account_server.ids import new_uuid7
from account_server.models import Account, utcnow
from account_server.security import hash_password
from sqlalchemy import select


class NoEmail(EmailProvider):
    def send_verification(self, email: str, token: str) -> None:
        raise AssertionError("Google flow must not send verification email")

    def send_password_reset(self, email: str, token: str) -> None:
        raise AssertionError("not used")


def settings(url: str) -> Settings:
    return Settings(database_url=url, smtp_host="127.0.0.1", smtp_port=1, smtp_username="", smtp_password="", smtp_from_email="test@jarvis.local", smtp_from_name="JARVIS TEST", smtp_use_ssl=False, smtp_use_starttls=False, smtp_timeout=1, email_delivery_enabled=False, public_base_url="http://test.local", google_auth_enabled=True, google_client_id="google-client-id", google_client_secret="google-client-secret", google_redirect_uri="http://127.0.0.1:8765/", access_ttl_seconds=900, refresh_ttl_seconds=3600, verification_ttl_seconds=3600, reset_ttl_seconds=3600, environment="test")


@unittest.skipUnless(os.getenv("ACCOUNT_TEST_DATABASE_URL"), "requires isolated PostgreSQL test database")
class GoogleOAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        def verify(raw, request, audience):
            if raw == "bad-signature-token-0001":
                raise ValueError("bad signature")
            email = "subject-conflict@example.test" if raw.startswith("subject-conflict") else f"{raw}@example.test"
            return {"iss": "https://accounts.google.com", "aud": audience, "exp": 4102444800, "sub": raw, "email": email, "email_verified": True}

        cls.validator = GoogleIdentityValidator("google-client-id", verifier=verify)
        cls.factory = build_session_factory(os.environ["ACCOUNT_TEST_DATABASE_URL"])
        cls.app = create_app(settings(os.environ["ACCOUNT_TEST_DATABASE_URL"]), email_provider=NoEmail(), google_validator=cls.validator)
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        dispose_session_factory(cls.factory)
        dispose_session_factory(cls.app.state.account_session_factory)

    def test_new_identity_creates_account_and_session(self) -> None:
        response = self.client.post("/api/v1/auth/google/exchange", json={"id_token": "subject-new-identity-0001"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["access_token"])
        repeated = self.client.post("/api/v1/auth/google/exchange", json={"id_token": "subject-new-identity-0001"})
        self.assertEqual(repeated.status_code, 200)

    def test_existing_email_conflict_is_not_auto_linked(self) -> None:
        email = "subject-conflict@example.test"
        with self.factory() as db:
            existing = db.scalar(select(Account).where(Account.email_normalized == email))
            if not existing:
                db.add(Account(id=new_uuid7(), email=email, email_normalized=email, password_hash=hash_password("ValidPassword123"), email_verified_at=utcnow(), status="active"))
                db.commit()
        response = self.client.post("/api/v1/auth/google/exchange", json={"id_token": "subject-conflict-identity-0001"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["error"]["code"], "google_email_conflict")

    def test_invalid_google_identity_is_rejected(self) -> None:
        response = self.client.post("/api/v1/auth/google/exchange", json={"id_token": "bad-signature-token-0001"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["error"]["code"], "invalid_google_identity")


class GoogleValidatorTests(unittest.TestCase):
    def test_unverified_email_and_wrong_issuer_are_rejected(self) -> None:
        for claims in (
            {"iss": "https://accounts.google.com", "sub": "x", "email": "x@example.test", "email_verified": False},
            {"iss": "https://evil.example", "sub": "x", "email": "x@example.test", "email_verified": True},
        ):
            validator = GoogleIdentityValidator("client", verifier=lambda *args, _claims=claims, **kwargs: _claims)
            with self.assertRaises(GoogleIdentityError):
                validator.validate("token")


if __name__ == "__main__":
    unittest.main()

