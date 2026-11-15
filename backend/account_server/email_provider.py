from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from html import escape


class EmailDeliveryError(RuntimeError):
    pass


class EmailProvider:
    def send_verification(self, email: str, token: str) -> None:
        raise NotImplementedError

    def send_password_reset(self, email: str, token: str) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class SMTPEmailProvider(EmailProvider):
    host: str
    port: int
    username: str = ""
    password: str = ""
    from_email: str = "no-reply@jarvis.local"
    from_name: str = "JARVIS ASSIST"
    use_ssl: bool = False
    use_starttls: bool = False
    timeout: float = 10.0
    delivery_enabled: bool = False
    public_base_url: str = ""

    def _send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        if not self.delivery_enabled:
            raise EmailDeliveryError("email delivery is disabled")
        message = EmailMessage()
        message["From"] = formataddr((self.from_name, self.from_email))
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
        try:
            smtp_type = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
            with smtp_type(self.host, self.port, timeout=self.timeout) as smtp:
                if self.use_starttls:
                    smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError("SMTP delivery failed") from exc

    def _link(self, path: str, token: str) -> str:
        if not self.public_base_url:
            raise EmailDeliveryError("public email action URL is not configured")
        return f"{self.public_base_url}{path}?token={token}"

    def send_verification(self, email: str, token: str) -> None:
        link = self._link("/account/verify-email", token)
        self._send(
            email,
            "Подтверждение регистрации в JARVIS",
            f"Здравствуйте!\n\nПодтвердите email в JARVIS: {link}\n\nСсылка действует ограниченное время и используется один раз.\n",
            f"<p>Здравствуйте!</p><p>Подтвердите email в JARVIS:</p><p><a href=\"{escape(link, quote=True)}\">Подтвердить email</a></p><p>Если кнопка не работает, используйте ссылку:<br>{escape(link)}</p><p>Ссылка действует ограниченное время и используется один раз.</p>",
        )

    def send_password_reset(self, email: str, token: str) -> None:
        link = self._link("/account/reset-password", token)
        self._send(
            email,
            "Восстановление пароля JARVIS",
            f"Здравствуйте!\n\nДля восстановления пароля откройте: {link}\n\nСсылка действует ограниченное время и используется один раз.\n",
            f"<p>Здравствуйте!</p><p>Для восстановления пароля JARVIS:</p><p><a href=\"{escape(link, quote=True)}\">Восстановить пароль</a></p><p>Если кнопка не работает, используйте ссылку:<br>{escape(link)}</p><p>Ссылка действует ограниченное время и используется один раз.</p>",
        )
