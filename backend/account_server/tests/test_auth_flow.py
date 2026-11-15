from __future__ import annotations

import os
import unittest
import uuid

from fastapi.testclient import TestClient

from account_server.app import create_app
from account_server.config import Settings
from account_server.database import dispose_session_factory
from account_server.email_provider import EmailProvider


class CaptureEmailProvider(EmailProvider):
    def __init__(self) -> None:
        self.verification: dict[str, str] = {}
        self.reset: dict[str, str] = {}

    def send_verification(self, email: str, token: str) -> None:
        self.verification[email] = token

    def send_password_reset(self, email: str, token: str) -> None:
        self.reset[email] = token


@unittest.skipUnless(os.getenv("ACCOUNT_TEST_DATABASE_URL"), "requires isolated PostgreSQL test database")
class AccountServerFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mail = CaptureEmailProvider()
        cls.settings = Settings(
            database_url=os.environ["ACCOUNT_TEST_DATABASE_URL"], smtp_host="127.0.0.1", smtp_port=1,
            smtp_username="", smtp_password="", smtp_from_email="test@jarvis.local", smtp_from_name="JARVIS TEST",
            smtp_use_ssl=False, smtp_use_starttls=False, smtp_timeout=1, email_delivery_enabled=False,
            public_base_url="http://test.local", access_ttl_seconds=900, refresh_ttl_seconds=3600,
            google_auth_enabled=False, google_client_id="", google_client_secret="", google_redirect_uri="http://127.0.0.1:8765/",
            verification_ttl_seconds=3600, reset_ttl_seconds=3600, environment="test",
        )
        cls.app = create_app(cls.settings, email_provider=cls.mail)
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        dispose_session_factory(cls.app.state.account_session_factory)

    @staticmethod
    def email(label: str) -> str:
        return f"phase2-{label}-{uuid.uuid4().hex[:12]}@example.test"

    def test_full_auth_flow_and_refresh_reuse(self) -> None:
        email = self.email("flow")
        password = "ValidPassword123"
        response = self.client.post("/api/v1/auth/register", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 202)
        response = self.client.post("/api/v1/auth/verify-email", json={"token": self.mail.verification[email]})
        self.assertEqual(response.status_code, 200)
        login = self.client.post("/api/v1/auth/login", json={"email": email, "password": password, "device_name": "Test Windows"})
        self.assertEqual(login.status_code, 200)
        tokens = login.json()
        self.assertTrue(tokens["access_token"])
        old_refresh = tokens["refresh_token"]
        refreshed = self.client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        self.assertEqual(refreshed.status_code, 200)
        self.assertNotEqual(refreshed.json()["refresh_token"], old_refresh)
        reused = self.client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        self.assertEqual(reused.status_code, 401)
        self.assertEqual(reused.json()["detail"]["error"]["code"], "token_reuse")

    def test_profile_devices_and_idor_protection(self) -> None:
        email = self.email("idor")
        password = "ValidPassword123"
        self.client.post("/api/v1/auth/register", json={"email": email, "password": password})
        self.client.post("/api/v1/auth/verify-email", json={"token": self.mail.verification[email]})
        login = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        profile = self.client.get("/api/v1/account/profile", headers=headers)
        devices = self.client.get("/api/v1/account/devices", headers=headers)
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(devices.status_code, 200)
        device_id = devices.json()["devices"][0]["id"]
        self.assertEqual(self.client.post(f"/api/v1/account/devices/{device_id}/revoke", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/account/profile", headers=headers).status_code, 401)

    def test_password_reset_is_one_time(self) -> None:
        email = self.email("reset")
        password = "ValidPassword123"
        self.client.post("/api/v1/auth/register", json={"email": email, "password": password})
        self.client.post("/api/v1/auth/verify-email", json={"token": self.mail.verification[email]})
        self.client.post("/api/v1/auth/password-reset/request", json={"email": email})
        token = self.mail.reset[email]
        response = self.client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "password": "NewValidPassword123"})
        self.assertEqual(response.status_code, 200)
        reused = self.client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "password": "OtherValidPassword123"})
        self.assertEqual(reused.status_code, 400)


if __name__ == "__main__":
    unittest.main()

