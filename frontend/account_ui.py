"""Jarvis-native Account UI for Local Mode and the future Account Server.

The dialogs deliberately use an explicit unavailable provider today. They never
pretend that registration, login or email delivery succeeded.
"""

from __future__ import annotations

import re
from typing import Callable

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from account.application.account_coordinator import AccountCoordinator
from account.application.auth_client import AuthError, AuthResult
from account.domain.enums import AccountLifecycleState, SyncState


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MIN_PASSWORD_LENGTH = 12


class GoogleLoginWorker(QThread):
    completed = Signal(object)

    def __init__(self, coordinator: AccountCoordinator) -> None:
        super().__init__()
        self.coordinator = coordinator

    def run(self) -> None:
        try:
            result = self.coordinator.login_with_google()
        except Exception as error:
            result = AuthResult(
                ok=False,
                error=AuthError(
                    "google_ui_error",
                    "Не удалось завершить вход через Google. Jarvis продолжает работать локально.",
                    retryable=True,
                    details={"type": type(error).__name__},
                ),
            )
        self.completed.emit(result)


class AccountDialog(QDialog):
    def __init__(self, title: str, coordinator: AccountCoordinator, parent=None) -> None:
        super().__init__(parent)
        self.coordinator = coordinator
        self._google_worker: GoogleLoginWorker | None = None
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setStyleSheet(
            """
            QDialog { background: rgba(20,24,30,245); color: white; }
            QLabel { color: white; }
            QLabel#accountHint { color: rgba(255,255,255,0.66); }
            QLabel#accountStatus { color: #00AAFF; min-height: 34px; }
            QLineEdit { background: rgba(255,255,255,0.10); color: white;
                border: 1px solid rgba(255,255,255,0.24); border-radius: 8px; padding: 9px; }
            QLineEdit:focus { border: 1px solid #00AAFF; }
            QPushButton, QDialogButtonBox QPushButton { background: #00AAFF;
                color: #071018; border: none; border-radius: 8px; padding: 9px 14px; }
            QPushButton:hover, QDialogButtonBox QPushButton:hover { background: #33BBFF; }
            QPushButton:pressed, QDialogButtonBox QPushButton:pressed { background: #0088CC; }
            QPushButton:disabled, QDialogButtonBox QPushButton:disabled { background: rgba(0,170,255,0.24); color: rgba(255,255,255,0.45); }
            QPushButton#secondary, QToolButton#link { background: transparent; color: #00AAFF; border: none; }
            QCheckBox { color: rgba(255,255,255,0.82); }
            """
        )
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 22, 24, 22)
        heading = QLabel(title.upper())
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.root.addWidget(heading)
        self.status = QLabel()
        self.status.setObjectName("accountStatus")
        self.status.setWordWrap(True)
        self.root.addWidget(self.status)

    def show_result(self, result: AuthResult) -> None:
        if result.ok:
            self.status.setText("Операция подтверждена сервером.")
            self.status.setStyleSheet("color: #7dffb2; min-height: 34px;")
        elif result.error:
            self.status.setText(result.error.message)
            self.status.setStyleSheet("color: #ff9ba8; min-height: 34px;")

    @staticmethod
    def password_valid(value: str) -> bool:
        return len(value) >= MIN_PASSWORD_LENGTH

    @staticmethod
    def email_valid(value: str) -> bool:
        return bool(EMAIL_RE.fullmatch(value.strip()))

    def local_mode(self) -> None:
        self.coordinator.logout_local()
        self.status.setText("LOCAL_ONLY: аккаунт не подключён. Jarvis продолжает работать локально.")


class AccountLoginDialog(AccountDialog):
    create_requested = Signal()
    reset_requested = Signal()
    authenticated = Signal()

    def __init__(self, coordinator: AccountCoordinator, parent=None) -> None:
        super().__init__("Вход в аккаунт", coordinator, parent)
        self.root.insertWidget(1, QLabel("Подключение аккаунта опционально. Local Mode не требует входа."), 0, Qt.AlignmentFlag.AlignLeft)
        form = QFormLayout()
        self.email = QLineEdit()
        self.email.setPlaceholderText("name@example.com")
        saved_email = coordinator.context().account.email
        if saved_email:
            self.email.setText(saved_email)
        self.password = QLineEdit()
        self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        toggle = QToolButton()
        toggle.setText("Показать")
        toggle.setCheckable(True)
        toggle.toggled.connect(lambda checked: (
            self.password.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password),
            toggle.setText("Скрыть" if checked else "Показать"),
        ))
        password_row = QHBoxLayout()
        password_row.addWidget(self.password, 1)
        password_row.addWidget(toggle)
        form.addRow("Email", self.email)
        form.addRow("Пароль", password_row)
        self.root.addLayout(form)
        actions = QHBoxLayout()
        login = QPushButton("Войти")
        login.clicked.connect(self.submit)
        forgot = QToolButton()
        forgot.setObjectName("link")
        forgot.setText("Забыли пароль?")
        forgot.clicked.connect(self.reset_requested.emit)
        actions.addWidget(login)
        actions.addWidget(forgot)
        self.root.addLayout(actions)
        google = QPushButton("Войти через Google")
        google.setObjectName("secondary")
        google.clicked.connect(self.submit_google)
        self.root.addWidget(google)
        create = QToolButton()
        create.setObjectName("link")
        create.setText("Создать аккаунт")
        create.clicked.connect(self.create_requested.emit)
        self.root.addWidget(create, 0, Qt.AlignmentFlag.AlignLeft)
        local = QPushButton("Продолжить в Local Mode")
        local.setObjectName("secondary")
        local.clicked.connect(self.local_mode)
        self.root.addWidget(local)

    def submit(self) -> None:
        email = self.email.text().strip()
        password = self.password.text()
        if not self.email_valid(email):
            self.status.setText("Введите корректный email.")
            return
        if not password:
            self.status.setText("Введите пароль.")
            return
        self.status.setText("Проверка данных через Account Server…")
        result = self.coordinator.auth_provider.login(email, password)
        self.show_result(result)
        if result.ok:
            try:
                self.coordinator.accept_auth_result(result)
                self.authenticated.emit()
                self.accept()
            except (KeyError, TypeError, ValueError) as error:
                self.status.setText(f"Сервер вернул неполное состояние сессии: {error}")

    def submit_google(self) -> None:
        if self._google_worker and self._google_worker.isRunning():
            return
        self.status.setText("Открытие системного браузера для Google…")
        self._google_worker = GoogleLoginWorker(self.coordinator)
        self._google_worker.completed.connect(self.google_completed)
        self._google_worker.start()

    def google_completed(self, result: AuthResult) -> None:
        self.show_result(result)
        self._google_worker = None
        if result.ok:
            self.authenticated.emit()
            self.accept()


class AccountRegisterDialog(AccountDialog):
    login_requested = Signal()

    def __init__(self, coordinator: AccountCoordinator, parent=None) -> None:
        super().__init__("Создать аккаунт", coordinator, parent)
        hint = QLabel("Регистрация станет доступна после подключения Account Server.")
        hint.setObjectName("accountHint")
        hint.setWordWrap(True)
        self.root.insertWidget(1, hint)
        form = QFormLayout()
        self.email = QLineEdit()
        self.email.setPlaceholderText("name@example.com")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText(f"Не менее {MIN_PASSWORD_LENGTH} символов")
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Email", self.email)
        form.addRow("Пароль", self.password)
        form.addRow("Повтор пароля", self.confirm)
        self.root.addLayout(form)
        self.terms = QCheckBox("Согласие с условиями появится после утверждения документов")
        self.terms.setEnabled(False)
        self.root.addWidget(self.terms)
        create = QPushButton("Создать аккаунт")
        create.clicked.connect(self.submit)
        self.root.addWidget(create)
        login = QToolButton()
        login.setObjectName("link")
        login.setText("Вернуться ко входу")
        login.clicked.connect(self.login_requested.emit)
        self.root.addWidget(login, 0, Qt.AlignmentFlag.AlignLeft)

    def submit(self) -> None:
        email = self.email.text().strip()
        password = self.password.text()
        if not self.email_valid(email):
            self.status.setText("Введите корректный email.")
            return
        if not self.password_valid(password):
            self.status.setText(f"Пароль должен содержать минимум {MIN_PASSWORD_LENGTH} символов.")
            return
        if password != self.confirm.text():
            self.status.setText("Пароли не совпадают.")
            return
        self.status.setText("Запрос регистрации через Account Server…")
        self.show_result(self.coordinator.auth_provider.register(email, password))


class EmailVerificationDialog(AccountDialog):
    def __init__(self, coordinator: AccountCoordinator, email: str = "", parent=None) -> None:
        super().__init__("Подтверждение Email", coordinator, parent)
        self.email_value = email
        hint = QLabel(f"Введите код подтверждения для {email or 'вашего email'}.")
        hint.setObjectName("accountHint")
        hint.setWordWrap(True)
        self.root.insertWidget(1, hint)
        self.code = QLineEdit()
        self.code.setPlaceholderText("Код подтверждения")
        self.root.addWidget(self.code)
        verify = QPushButton("Подтвердить Email")
        verify.clicked.connect(self.submit)
        resend = QPushButton("Отправить код повторно")
        resend.setObjectName("secondary")
        resend.clicked.connect(self.resend)
        self.root.addWidget(verify)
        self.root.addWidget(resend)

    def submit(self) -> None:
        if not self.code.text().strip():
            self.status.setText("Введите код подтверждения.")
            return
        self.show_result(self.coordinator.auth_provider.verify_email(self.email_value, self.code.text().strip()))

    def resend(self) -> None:
        self.show_result(self.coordinator.auth_provider.verify_email(self.email_value, ""))


class PasswordResetDialog(AccountDialog):
    def __init__(self, coordinator: AccountCoordinator, parent=None) -> None:
        super().__init__("Восстановление пароля", coordinator, parent)
        hint = QLabel("Для восстановления нужен действительный ответ Account Server.")
        hint.setObjectName("accountHint")
        hint.setWordWrap(True)
        self.root.insertWidget(1, hint)
        form = QFormLayout()
        self.email = QLineEdit()
        self.email.setPlaceholderText("name@example.com")
        self.code = QLineEdit()
        self.code.setPlaceholderText("Код восстановления")
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setPlaceholderText(f"Не менее {MIN_PASSWORD_LENGTH} символов")
        form.addRow("Email", self.email)
        form.addRow("Код", self.code)
        form.addRow("Новый пароль", self.new_password)
        self.root.addLayout(form)
        request = QPushButton("Запросить код")
        request.clicked.connect(self.request_code)
        confirm = QPushButton("Установить новый пароль")
        confirm.clicked.connect(self.confirm_reset)
        self.root.addWidget(request)
        self.root.addWidget(confirm)

    def request_code(self) -> None:
        if not self.email_valid(self.email.text()):
            self.status.setText("Введите корректный email.")
            return
        self.show_result(self.coordinator.auth_provider.request_password_reset(self.email.text().strip()))

    def confirm_reset(self) -> None:
        if not self.email_valid(self.email.text()) or not self.code.text().strip() or not self.password_valid(self.new_password.text()):
            self.status.setText("Проверьте email, код и требования к новому паролю.")
            return
        self.show_result(self.coordinator.auth_provider.confirm_password_reset(self.email.text().strip(), self.code.text().strip(), self.new_password.text()))


class AccountCenterDialog(AccountDialog):
    def __init__(self, coordinator: AccountCoordinator, parent=None) -> None:
        super().__init__("Аккаунт Jarvis", coordinator, parent)
        context = coordinator.context()
        lifecycle = context.lifecycle.value
        if lifecycle == AccountLifecycleState.LOCAL_ONLY.value:
            display_state = "Локальный режим"
            sync_state = "не настроена"
        else:
            display_state = lifecycle
            sync_state = context.sync_state.value
        self.account_info = QLabel(
            f"Состояние: {display_state}\n"
            f"Аккаунт: {context.account.email or 'не подключён'}\n"
            f"Синхронизация: {sync_state}\n"
            "Account Server: не подключён"
        )
        self.account_info.setObjectName("accountHint")
        self.account_info.setWordWrap(True)
        self.root.insertWidget(1, self.account_info)
        self.status.setText(
            "Аккаунт подключён. Jarvis продолжает работать локально; синхронизация включается отдельно."
            if context.account.account_id
            else "Jarvis работает локально. Войдите в аккаунт, чтобы сохранять "
            "историю в облаке и синхронизировать данные между устройствами."
        )
        if context.account.account_id:
            edit_profile = QPushButton("Редактировать профиль")
            edit_profile.clicked.connect(self._edit_profile)
            logout = QPushButton("Выйти из аккаунта")
            logout.clicked.connect(self._logout_account)
            local = QPushButton("Продолжить в Local Mode")
            local.setObjectName("secondary")
            local.clicked.connect(self.local_mode)
            for button in (edit_profile, logout, local):
                self.root.addWidget(button)
        else:
            login = QPushButton("Войти в аккаунт")
            login.clicked.connect(lambda: self.open_dialog(AccountLoginDialog))
            register = QPushButton("Создать аккаунт")
            register.clicked.connect(lambda: self.open_dialog(AccountRegisterDialog))
            verify = QPushButton("Подтвердить Email")
            verify.setEnabled(False)
            reset = QPushButton("Восстановить пароль")
            reset.clicked.connect(lambda: self.open_dialog(PasswordResetDialog))
            local = QPushButton("Оставаться в Local Mode")
            local.setObjectName("secondary")
            local.clicked.connect(self.local_mode)
            for button in (login, register, verify, reset, local):
                self.root.addWidget(button)

    def open_dialog(self, dialog_type: Callable[..., AccountDialog]) -> None:
        dialog = dialog_type(self.coordinator, self)
        if isinstance(dialog, AccountLoginDialog):
            dialog.authenticated.connect(self._account_authenticated)
            dialog.create_requested.connect(lambda: self._replace(dialog, AccountRegisterDialog))
            dialog.reset_requested.connect(lambda: self._replace(dialog, PasswordResetDialog))
        elif isinstance(dialog, AccountRegisterDialog):
            dialog.login_requested.connect(lambda: self._replace(dialog, AccountLoginDialog))
        dialog.exec()

    def _replace(self, old: QDialog, dialog_type: Callable[..., AccountDialog]) -> None:
        old.close()
        self.open_dialog(dialog_type)

    def _account_authenticated(self) -> None:
        context = self.coordinator.context()
        self.account_info.setText(
            f"Состояние: авторизован\n"
            f"Аккаунт: {context.account.email or 'подключён'}\n"
            f"Синхронизация: {context.sync_state.value}\n"
            "Account Server: подключён"
        )
        self.status.setText("Аккаунт успешно подключён. Jarvis продолжает работать в Local Mode до включения синхронизации.")

    def _edit_profile(self) -> None:
        editor = getattr(self.parent(), "show_user_profile", None)
        if callable(editor):
            editor()
        else:
            self.status.setText("Редактор локального профиля недоступен в этом окне.")

    def _logout_account(self) -> None:
        result = self.coordinator.auth_provider.logout()
        self.coordinator.logout_local()
        if result.ok:
            self.status.setText("Вы вышли из аккаунта. Локальная история сохранена.")
        elif result.error:
            self.status.setText(f"Сессия очищена локально: {result.error.message}")
        self.accept()
