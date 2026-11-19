"""Local user profile editor, ported from Crazy Tad's profile UX."""

from pathlib import Path
import re
import time

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QImage, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QDialogButtonBox, QFileDialog, QMessageBox, QWidget,
    QSlider,
)


class AvatarCropPreview(QWidget):
    """Small square cropper with drag and wheel zoom, like the donor dialog."""

    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.image = image
        self.zoom = 1.0
        self.offset = QPoint(0, 0)
        self.last_pos = None
        self.setFixedSize(240, 240)
        self.setMouseTracking(True)

    def _scaled(self):
        side = max(1, min(self.image.width(), self.image.height()))
        scale = 240.0 / side * self.zoom
        return self.image.scaled(
            max(1, round(self.image.width() * scale)),
            max(1, round(self.image.height() * scale)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _clamp(self):
        scaled = self._scaled()
        base_x = (240 - scaled.width()) // 2
        base_y = (240 - scaled.height()) // 2
        self.offset.setX(max(240 - scaled.width() - base_x, min(-base_x, self.offset.x())))
        self.offset.setY(max(240 - scaled.height() - base_y, min(-base_y, self.offset.y())))

    def paintEvent(self, event):
        del event
        scaled = self._scaled()
        self._clamp()
        x = (240 - scaled.width()) // 2 + self.offset.x()
        y = (240 - scaled.height()) // 2 + self.offset.y()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        painter.drawImage(x, y, scaled)
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.setPen(Qt.NoPen)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setBrush(Qt.GlobalColor.black)
        painter.setOpacity(0.48)
        outer = self.rect()
        painter.drawRect(outer)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.drawEllipse(0, 0, 240, 240)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setOpacity(1.0)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawEllipse(1, 1, 238, 238)
        painter.end()

    def mousePressEvent(self, event):
        self.last_pos = event.position().toPoint()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.last_pos is not None:
            current = event.position().toPoint()
            self.offset += current - self.last_pos
            self.last_pos = current
            self._clamp()
            self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        self.last_pos = None
        event.accept()

    def wheelEvent(self, event):
        self.zoom = max(1.0, min(4.0, self.zoom + (0.1 if event.angleDelta().y() > 0 else -0.1)))
        self._clamp()
        self.update()
        event.accept()

    def cropped_image(self):
        scaled = self._scaled()
        self._clamp()
        x = (240 - scaled.width()) // 2 + self.offset.x()
        y = (240 - scaled.height()) // 2 + self.offset.y()
        factor = 512.0 / 240.0
        output = QImage(512, 512, QImage.Format.Format_ARGB32_Premultiplied)
        output.fill(Qt.GlobalColor.transparent)
        painter = QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(round(x * factor), round(y * factor), scaled.scaled(
            round(scaled.width() * factor), round(scaled.height() * factor),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        painter.end()
        return output


class AvatarCropDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Кадрирование аватара")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Перетащите изображение. Колесо мыши — масштаб."))
        self.preview = AvatarCropPreview(image, self)
        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class UserProfileDialog(QDialog):
    """Edit the single local Jarvis user profile."""

    saved = Signal(dict)

    def __init__(self, settings, accent="#00ebf5", parent=None, glass_stylesheet=""):
        super().__init__(parent)
        self.settings = settings
        self.accent = accent
        self.glass_stylesheet = glass_stylesheet
        self.avatar_path = str(settings.value("profile_avatar_path", ""))
        self.setWindowTitle("Мой профиль")
        self.setMinimumWidth(440)
        self.setModal(True)
        self._build()

    def _build(self):
        default_style = f"""
            QDialog {{ background: rgba(20, 24, 30, 245); color: white; }}
            QLabel {{ color: white; }}
            QLineEdit {{ background: rgba(255,255,255,0.12); color: white;
                border: 1px solid rgba(255,255,255,0.24); border-radius: 8px; padding: 8px; }}
            QPushButton, QDialogButtonBox QPushButton {{ background: {self.accent};
                color: #071018; border: none; border-radius: 8px; padding: 8px 14px; }}
            QPushButton:hover, QDialogButtonBox QPushButton:hover {{ background: {self.accent}; color: #071018; }}
        """
        self.setStyleSheet(self.glass_stylesheet or default_style)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        title = QLabel("МОЙ ПРОФИЛЬ")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        self.avatar = QLabel()
        self.avatar.setFixedSize(120, 120)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setStyleSheet("border-radius: 60px; background: #3b4652; color: white; font-size: 42px; font-weight: bold;")
        self.avatar.setMask(QRegion(0, 0, 120, 120, QRegion.RegionType.Ellipse))
        root.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignHCenter)
        self._refresh_avatar()

        avatar_buttons = QHBoxLayout()
        choose = QPushButton("Выбрать аватар")
        choose.clicked.connect(self._choose_avatar)
        remove = QPushButton("Удалить аватар")
        remove.clicked.connect(self._remove_avatar)
        avatar_buttons.addWidget(choose)
        avatar_buttons.addWidget(remove)
        root.addLayout(avatar_buttons)

        form = QFormLayout()
        self.name_input = QLineEdit(str(self.settings.value("profile_display_name", "Данил")))
        self.username_input = QLineEdit(str(self.settings.value("profile_username", "sheff")))
        self.username_input.setPlaceholderText("без @")
        self.email_input = QLineEdit(str(self.settings.value("profile_email", "")))
        self.email_input.setPlaceholderText("name@example.com")
        self.age_input = QLineEdit(str(self.settings.value("profile_age", "")))
        self.age_input.setPlaceholderText("например, 30")
        self.address_input = QLineEdit(str(self.settings.value("profile_address", "Данил")))
        self.address_input.setPlaceholderText("Как к вам обращаться")
        form.addRow("Имя:", self.name_input)
        form.addRow("Username:", self.username_input)
        form.addRow("Электронная почта:", self.email_input)
        form.addRow("Возраст:", self.age_input)
        form.addRow("Как обращаться:", self.address_input)
        root.addLayout(form)

        info = QLabel("Стабильный ID: user:danil\nРоль: Пользователь")
        info.setStyleSheet("color: rgba(255,255,255,0.62); padding-top: 8px;")
        root.addWidget(info)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _refresh_avatar(self):
        path = Path(self.avatar_path) if self.avatar_path else None
        if path and path.exists():
            pixmap = QPixmap(str(path)).scaled(
                120, 120, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.avatar.setPixmap(pixmap)
        else:
            self.avatar.clear()
            self.avatar.setText((self.name_input.text() if hasattr(self, "name_input") else "Д")[:1].upper())

    def _choose_avatar(self):
        selected, _ = QFileDialog.getOpenFileName(
            self, "Выбрать аватар", "", "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not selected:
            return
        image = QImage(selected)
        if image.isNull():
            QMessageBox.warning(self, "Аватар", "Не удалось открыть изображение.")
            return
        crop = AvatarCropDialog(image, self)
        if crop.exec() != QDialog.DialogCode.Accepted:
            return
        target_dir = Path(__file__).resolve().parent / "assets" / "profile"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"user_danil_{time.time_ns()}.png"
        if not crop.preview.cropped_image().save(str(target), "PNG"):
            QMessageBox.warning(self, "Аватар", "Не удалось сохранить аватар.")
            return
        self.avatar_path = str(target)
        self._refresh_avatar()

    def _remove_avatar(self):
        self.avatar_path = ""
        self._refresh_avatar()

    def _save(self):
        name = self.name_input.text().strip()
        username = self.username_input.text().strip().lstrip("@").lower()
        if not name or not re.fullmatch(r"[a-z0-9_]{2,32}", username):
            QMessageBox.warning(self, "Профиль", "Введите имя и username из 2–32 латинских символов, цифр или _. ")
            return
        profile = {
            "entity_id": "user:danil",
            "display_name": name,
            "username": username,
            "avatar_path": self.avatar_path,
            "role": "Пользователь",
            "email": self.email_input.text().strip(),
            "age": self.age_input.text().strip(),
            "address": self.address_input.text().strip(),
        }
        for key, value in (
            ("profile_display_name", name),
            ("profile_username", username),
            ("profile_avatar_path", self.avatar_path),
            ("profile_email", self.email_input.text().strip()),
            ("profile_age", self.age_input.text().strip()),
            ("profile_address", self.address_input.text().strip()),
        ):
            self.settings.setValue(key, value)
        self.settings.sync()
        self.saved.emit(profile)
        self.accept()
