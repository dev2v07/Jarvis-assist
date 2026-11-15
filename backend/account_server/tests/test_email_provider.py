from __future__ import annotations

import unittest
from unittest.mock import patch

from account_server.email_provider import EmailDeliveryError, SMTPEmailProvider


class FakeSMTP:
    sent = None
    logged_in = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, message):
        FakeSMTP.sent = message


class EmailProviderTests(unittest.TestCase):
    def test_yandex_ssl_provider_logs_in_and_sends_linked_html_text(self) -> None:
        provider = SMTPEmailProvider(
            "smtp.yandex.ru", 465, "jarvis@tandemarketing.ru", "app-secret",
            "jarvis@tandemarketing.ru", "JARVIS ASSIST", True, False, 10, True,
            "https://account.example.test",
        )
        with patch("account_server.email_provider.smtplib.SMTP_SSL", FakeSMTP):
            provider.send_verification("recipient@example.test", "verification-token")
        self.assertEqual(FakeSMTP.sent["From"], "JARVIS ASSIST <jarvis@tandemarketing.ru>")
        self.assertEqual(FakeSMTP.sent["Subject"], "Подтверждение регистрации в JARVIS")
        self.assertIn("https://account.example.test/account/verify-email?token=verification-token", FakeSMTP.sent.get_body(preferencelist=("plain",)).get_content())
        self.assertNotIn("app-secret", FakeSMTP.sent.as_string())

    def test_disabled_delivery_never_reports_success(self) -> None:
        provider = SMTPEmailProvider("smtp.yandex.ru", 465, "", "", "jarvis@tandemarketing.ru", "JARVIS ASSIST", True, False, 10, False, "https://account.example.test")
        with self.assertRaises(EmailDeliveryError):
            provider.send_password_reset("recipient@example.test", "token")


if __name__ == "__main__":
    unittest.main()

