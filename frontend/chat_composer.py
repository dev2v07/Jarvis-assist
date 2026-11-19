"""Native Jarvis chat composer adapted from the Crazy Tad chat flow.

This module deliberately owns only draft composition. Message transport,
history, reactions, replies and media playback will be connected by the chat
store layer; the composer never writes into the donor project or executes a
file from a picker without an explicit user action.
"""

from __future__ import annotations

import mimetypes
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, QSize, QPoint, QUrl, QTimer, QVariantAnimation, QAbstractAnimation
from PySide6.QtGui import QIcon, QMovie, QPixmap, QImage, QTextCursor, QTextImageFormat, QTextFormat, QTextDocument, QColor, QPainter, QPen
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class DraftAttachment:
    """A transport-neutral attachment descriptor for the current draft."""

    path: str
    name: str
    media_type: str
    kind: str = "file"
    pack_id: str = ""
    item_id: str = ""
    send_mode: str = "file"
    emote: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AttachmentChip(QFrame):
    removed = Signal()

    def __init__(self, attachment: DraftAttachment, parent=None):
        super().__init__(parent)
        self.attachment = attachment
        self.setObjectName("attachmentChip")
        self.setStyleSheet(
            "QFrame#attachmentChip { background: rgba(255,255,255,0.08); "
            "border: 1px solid rgba(255,255,255,0.16); border-radius: 8px; }"
            "QFrame#attachmentChip QLabel { color: #d8e0ea; background: transparent; }"
            "QFrame#attachmentChip QToolButton#attachmentRemove { color: #cbd5e1; background: transparent; "
            "border: none; border-radius: 6px; padding: 2px; margin: 0; }"
            "QFrame#attachmentChip QToolButton#attachmentRemove:hover { background: rgba(255,90,90,0.24); }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 5, 4)
        layout.setSpacing(5)
        category = self._category_for(attachment)
        icon_path = Path(__file__).parent / "assets" / "CHAT" / "icons" / "attachments" / "svg" / f"{category}.svg"
        is_image = category == "image" and attachment.kind not in {"mult", "sticker"}
        preview_allowed = False
        try:
            preview_allowed = Path(attachment.path).is_file() and Path(attachment.path).stat().st_size <= 8 * 1024 * 1024
        except OSError:
            preview_allowed = False
        if is_image and preview_allowed:
            preview = QLabel()
            preview.setFixedSize(40, 40)
            preview.setPixmap(QPixmap(attachment.path).scaled(
                40, 40, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            ))
            preview.setStyleSheet("background: transparent; border-radius: 7px;")
            layout.addWidget(preview)
        elif icon_path.is_file():
            icon = QLabel()
            icon.setFixedSize(34, 34)
            icon.setPixmap(QIcon(str(icon_path)).pixmap(34, 34))
            icon.setStyleSheet("background: transparent; border: none;")
            layout.addWidget(icon)
        label = QLabel(attachment.name)
        label.setObjectName("attachmentName")
        label.setToolTip(attachment.path)
        label.setMaximumWidth(190)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        close = QToolButton()
        close.setObjectName("attachmentRemove")
        trash_path = Path(__file__).parent / "assets" / "trash.svg"
        if trash_path.is_file():
            close.setIcon(QIcon(str(trash_path)))
            close.setIconSize(QSize(16, 16))
        else:
            close.setText("×")
        close.setAutoRaise(True)
        close.setFixedSize(24, 24)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setToolTip("Удалить вложение из черновика")
        close.setAccessibleName("Удалить вложение")
        close.clicked.connect(self.removed)
        layout.addWidget(close)

    @staticmethod
    def _category_for(attachment: DraftAttachment) -> str:
        media = (attachment.media_type or "").lower()
        suffix = Path(attachment.name).suffix.lower()
        if attachment.kind in {"mult", "sticker"}:
            return "image"
        if media.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            return "image"
        if media.startswith("video/") or suffix in {".mp4", ".mov", ".webm", ".avi", ".mkv"}:
            return "video"
        if media.startswith("audio/") or suffix in {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}:
            return "audio"
        if suffix in {".zip", ".rar", ".7z", ".tar", ".gz"}:
            return "archive"
        if suffix in {".py", ".js", ".ts", ".json", ".html", ".css"}:
            return "code"
        if suffix in {".exe", ".msi", ".dll"}:
            return "application"
        return "document"


class VoiceActivityWidget(QWidget):
    """Compact ChatGPT-like recording strip driven by microphone amplitude."""

    def __init__(self, accent: str, parent=None):
        super().__init__(parent)
        self.accent = QColor(accent)
        self._level = 0.0
        self._phase = 0.0
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip("Идёт запись речи — нажмите stop для завершения")
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._phase = 0.0
        self._timer.start()
        self.update()

    def stop(self):
        self._timer.stop()
        self._level = 0.0
        self.update()

    def set_level(self, level: float):
        self._level = max(0.0, min(1.0, float(level)))
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.22) % (2 * 3.141592653589793)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = max(1, self.width())
        center_y = self.height() / 2
        count = max(18, min(72, width // 10))
        step = width / max(1, count - 1)
        for index in range(count):
            x = index * step
            wave = abs(__import__("math").sin(self._phase + index * 0.48))
            amplitude = 1.2 + (self._level * 13.0 * (0.35 + wave * 0.65))
            # Keep a visible idle breathing motion even for quiet speech;
            # microphone amplitude then expands the same dots immediately.
            amplitude += 1.2 * wave
            alpha = 105 + int(min(150, self._level * 150 + wave * 35))
            color = QColor(self.accent)
            color.setAlpha(alpha)
            painter.setPen(QPen(color, 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(x), int(center_y - amplitude), int(x), int(center_y + amplitude))
        painter.end()

class EmotePicker(QFrame):
    """Legacy fallback picker kept only for compatibility; semantic mults only."""

    selected = Signal(object)
    closed = Signal()

    EMOJI = ("😀", "😂", "😍", "🤖", "👍", "❤️", "🔥", "🎉", "😎", "🙌", "💡", "✅")

    def __init__(self, asset_root: Path, accent: str, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.asset_root = Path(asset_root)
        self.accent = accent
        self.setObjectName("emotePicker")
        self.setFixedWidth(360)
        self.setStyleSheet(
            f"QFrame#emotePicker {{ background: rgba(24,28,34,0.98); "
            f"border: 1px solid {accent}; border-radius: 12px; }}"
            "QPushButton { background: transparent; border: none; border-radius: 7px; padding: 5px; }"
            f"QPushButton:hover {{ background: {accent}; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        tabs = QHBoxLayout()
        self.mult_tab = QPushButton("Мульты")
        self.mult_tab.clicked.connect(lambda: self._show_page(0))
        tabs.addWidget(self.mult_tab)
        root.addLayout(tabs)
        self.pages = []
        for builder in (self._build_mult_page,):
            page = QWidget()
            builder(page)
            self.pages.append(page)
            root.addWidget(page)
        self._show_page(0)

    def _build_mult_page(self, page: QWidget):
        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setSpacing(5)
        files = sorted(
            path for path in (self.asset_root / "stickers").rglob("*")
            if path.is_file() and path.suffix.lower() in {".gif", ".png"}
        )
        for index, path in enumerate(files):
            button = QToolButton()
            button.setToolTip(path.stem)
            button.setFixedSize(52, 52)
            if path.suffix.lower() == ".gif":
                movie = QMovie(str(path))
                movie.setScaledSize(QSize(42, 42))
                button.setIcon(QIcon(movie.currentPixmap()))
                movie.frameChanged.connect(lambda _frame, m=movie, b=button: b.setIcon(QIcon(m.currentPixmap())))
                movie.start()
                button._jarvis_movie = movie
            else:
                button.setIcon(QIcon(str(path)))
            button.setIconSize(QSize(42, 42))
            descriptor = DraftAttachment(
                path=str(path), name=path.name,
                media_type=mimetypes.guess_type(path.name)[0] or "image/*",
                kind="mult", pack_id="crazy_tad", item_id=path.stem,
            )
            button.clicked.connect(lambda checked=False, item=descriptor: self.selected.emit(item))
            grid.addWidget(button, index // 6, index % 6)
        scroll.setWidget(content)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def _show_page(self, index: int):
        for page_index, page in enumerate(self.pages):
            page.setVisible(page_index == index)


class ChatComposer(QWidget):
    """Jarvis composer with attachments, emoji and mult draft support."""

    send_requested = Signal(str, object)
    cancel_requested = Signal()
    reply_cleared = Signal()
    voice_requested = Signal()
    voice_cancel_requested = Signal()
    voice_chat_requested = Signal()
    voice_chat_stop_requested = Signal()
    emote_requested = Signal()
    tool_requested = Signal(str)

    def __init__(self, asset_root: Path, accent: str, parent=None):
        super().__init__(parent)
        self.asset_root = Path(asset_root)
        self.accent = accent
        self.pending_attachments: list[DraftAttachment] = []
        self._inline_emotes: dict[str, tuple[QMovie, QLabel]] = {}
        self._inline_lottie: dict[str, QWebEngineView] = {}
        self._inline_fallbacks: dict[str, QLabel] = {}
        self._inline_positions: dict[str, int] = {}
        self._inline_emote_property = int(QTextFormat.Property.UserProperty) + 41
        self.reply_context: dict[str, Any] | None = None
        self.picker: EmotePicker | None = None
        self._picker_cursor: QTextCursor | None = None
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("chatComposer")
        self.setStyleSheet(
            f"QWidget#chatComposer {{ background: transparent; }}"
            f"QFrame#attachmentsPreview {{ background: transparent; border: none; }}"
            f"QWidget#attachmentsContent {{ background: transparent; }}"
            f"QToolButton#attachBtn, QToolButton#emojiBtn, QToolButton#voiceBtn, QToolButton#voiceChatBtn {{ background: transparent; border: none; color: #9aa4b2; padding: 0; border-radius: 6px; }}"
            f"QToolButton#attachBtn:hover, QToolButton#emojiBtn:hover, QToolButton#voiceBtn:hover, QToolButton#voiceChatBtn:hover {{ background: rgba(255,255,255,0.08); color: #e0e0e0; }}"
            f"QToolButton#voiceBtn[recording=\"true\"] {{ background: {self.accent}; color: #071116; border-radius: 8px; font-size: 16px; font-weight: 700; }}"
            f"QToolButton#voiceChatBtn[active=\"true\"] {{ background: {self.accent}; color: #071116; border-radius: 8px; font-weight: 700; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(5)
        self.reply_bar = QFrame()
        self.reply_bar.setVisible(False)
        reply_layout = QHBoxLayout(self.reply_bar)
        reply_layout.setContentsMargins(8, 4, 8, 4)
        self.reply_label = QLabel()
        reply_layout.addWidget(self.reply_label, 1)
        clear_reply = QToolButton()
        clear_reply.setText("×")
        clear_reply.clicked.connect(self.clear_reply)
        reply_layout.addWidget(clear_reply)
        root.addWidget(self.reply_bar)

        self.attachments_scroll = QScrollArea()
        self.attachments_scroll.setObjectName("attachmentsPreview")
        self.attachments_scroll.setVisible(False)
        self.attachments_scroll.setMaximumHeight(78)
        self.attachments_scroll.setMinimumHeight(0)
        self.attachments_scroll.setWidgetResizable(False)
        self.attachments_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.attachments_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.attachments_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.attachments_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.attachments_content = QWidget()
        self.attachments_content.setObjectName("attachmentsContent")
        self.attachments_content.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.attachments_layout = QHBoxLayout(self.attachments_content)
        self.attachments_layout.setContentsMargins(2, 12, 2, 0)
        self.attachments_layout.setSpacing(8)
        self.attachments_layout.addStretch()
        self.attachments_scroll.setWidget(self.attachments_content)
        root.addWidget(self.attachments_scroll)

        bar = QFrame()
        bar.setObjectName("composerBar")
        bar.setFixedHeight(58)
        bar.setStyleSheet(
            f"QFrame#composerBar {{ background: rgba(24,28,34,0.94); border: 1px solid rgba(255,255,255,0.14); border-radius: 12px; }}"
            f"QFrame#composerBar:focus-within {{ border: 1px solid {self.accent}; }}"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(5, 4, 5, 4)
        layout.setSpacing(4)
        self.attach_button = QToolButton()
        self.attach_button.setObjectName("attachBtn")
        self.attach_button.setIcon(QIcon(str(self.asset_root / "icons" / "добавить файл.svg")))
        self.attach_button.setIconSize(QSize(22, 22))
        self.attach_button.setToolTip("Прикрепить файл")
        self.attach_button.setFixedSize(36, 44)
        self.attach_button.clicked.connect(self.pick_files)
        layout.addWidget(self.attach_button)
        self.message_input = QTextEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Спросите JARVIS или дайте команду")
        self.message_input.setMinimumHeight(42)
        self.message_input.setMaximumHeight(52)
        self.message_input.setAcceptRichText(False)
        self.message_input.setFrameStyle(QFrame.Shape.NoFrame)
        self.message_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.message_input.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.message_input.setStyleSheet(
            f"QTextEdit#messageInput {{ background: transparent; border: none; border-radius: 0; padding: 8px 6px; color: #e0e0e0; font-size: 14px; }}"
            "QTextEdit#messageInput:focus { border: none; }"
        )
        self.message_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.message_input, 1)
        self.voice_visualizer = VoiceActivityWidget(self.accent, bar)
        self.voice_visualizer.setObjectName("voiceActivity")
        self.voice_visualizer.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.voice_visualizer.hide()
        layout.addWidget(self.voice_visualizer, 1)

        # Crazy Tad order: the editor sits between the file action and the
        # emoji/voice actions. Keeping these controls on the trailing side is
        # important because the donor picker is anchored to the emoji button.
        self.emote_button = QToolButton()
        self.emote_button.setObjectName("emojiBtn")
        self.emote_button.setIcon(QIcon(str(self.asset_root / "icons" / "эмодзи.svg")))
        self.emote_button.setIconSize(QSize(22, 22))
        self.emote_button.setFixedSize(34, 44)
        self.emote_button.setToolTip("Эмодзи и мульты")
        self.emote_button.clicked.connect(self.emote_requested)
        layout.addWidget(self.emote_button)
        self.voice_button = QToolButton()
        self.voice_button.setObjectName("voiceBtn")
        self._normal_voice_icon = QIcon(str(self.asset_root / "icons" / "микрофон.svg"))
        self._voice_stop_icon = QIcon(str(self.asset_root / "icons" / "stop.svg"))
        self.voice_button.setIcon(self._normal_voice_icon)
        self.voice_button.setIconSize(QSize(22, 22))
        self.voice_button.setText("")
        self.voice_button.setAccessibleName("Голосовой ввод")
        self.voice_button.setFixedSize(34, 44)
        self.voice_button.setToolTip("Голосовой ввод: начать или остановить запись")
        self.voice_button.clicked.connect(self.voice_requested)
        self.voice_button.installEventFilter(self)
        layout.addWidget(self.voice_button)
        self._voice_glow = QGraphicsDropShadowEffect(self.voice_button)
        self._voice_glow.setOffset(0, 0)
        self._voice_glow.setColor(QColor(self.accent))
        self._voice_glow.setBlurRadius(0)
        self._voice_glow.setEnabled(False)
        self.voice_button.setGraphicsEffect(self._voice_glow)
        self._voice_pulse = QVariantAnimation(self)
        self._voice_pulse.setStartValue(21)
        self._voice_pulse.setEndValue(27)
        self._voice_pulse.setDuration(620)
        self._voice_pulse.setLoopCount(-1)
        self._voice_pulse.valueChanged.connect(self._set_voice_icon_size)
        self.voice_chat_button = QToolButton()
        self.voice_chat_button.setObjectName("voiceChatBtn")
        self._voice_chat_icon = QIcon(str(self.asset_root / "icons" / "headphones.svg"))
        self.voice_chat_button.setIcon(self._voice_chat_icon)
        self.voice_chat_button.setIconSize(QSize(22, 22))
        self.voice_chat_button.setText("")
        self.voice_chat_button.setFixedSize(34, 44)
        self.voice_chat_button.setAccessibleName("Голосовой чат")
        self.voice_chat_button.setToolTip("Голосовой чат в этом диалоге")
        self.voice_chat_button.clicked.connect(self._toggle_voice_chat)
        layout.addWidget(self.voice_chat_button)
        self.send_button = QPushButton("➤")
        self.send_button.setObjectName("sendBtn")
        self.send_button.setText("")
        self.send_button.setIcon(QIcon(str(self.asset_root / "icons" / "отправка.svg")))
        self.send_button.setIconSize(QSize(36, 36))
        self.send_button.setFixedSize(42, 42)
        self.send_button.setStyleSheet(
            "QPushButton#sendBtn { background: transparent; color: #e0e0e0; border: none; border-radius: 8px; }"
            "QPushButton#sendBtn:hover { background: rgba(255,255,255,0.08); border: none; }"
            "QPushButton#sendBtn:pressed { background: rgba(255,255,255,0.14); border: none; }"
        )
        self._send_press_anim = QVariantAnimation(self)
        self._send_press_anim.setDuration(110)
        self._send_press_anim.valueChanged.connect(self._set_send_icon_size)
        self.send_button.pressed.connect(self._send_button_pressed)
        self.send_button.released.connect(self._send_button_released)
        self.send_button.clicked.connect(self.submit)
        layout.addWidget(self.send_button)
        root.addWidget(bar)
        self.message_input.installEventFilter(self)
        self.message_input.textChanged.connect(self._reposition_inline_emotes)
        self.message_input.document().contentsChange.connect(self._on_contents_change)
        self._normal_send_icon = QIcon(str(self.asset_root / "icons" / "отправка.svg"))
        self._sending = False
        self._voice_recording = False
        self._voice_chat_active = False
        self.installEventFilter(self)
        self.voice_visualizer.installEventFilter(self)

    def set_sending(self, sending: bool, error: str = ""):
        """Give the user an immediate, visible send state."""
        self._sending = bool(sending)
        self.send_button.setEnabled(True)
        self.send_button.setProperty("sending", bool(sending))
        self.send_button.style().unpolish(self.send_button)
        self.send_button.style().polish(self.send_button)
        if sending:
            self.send_button.setToolTip("Jarvis обрабатывает сообщение…")
            self.send_button.setText("")
            self.send_button.setIcon(self._voice_stop_icon)
            self.send_button.setIconSize(QSize(22, 22))
        else:
            self._send_press_anim.stop()
            self.send_button.setText("")
            self.send_button.setIcon(self._normal_send_icon)
            self.send_button.setIconSize(QSize(36, 36))
            self.send_button.setToolTip(error or "Отправить")

    def _set_send_icon_size(self, value):
        size = max(26, min(36, int(value)))
        self.send_button.setIconSize(QSize(size, size))

    def _animate_send_icon(self, start: int, end: int):
        self._send_press_anim.stop()
        self._send_press_anim.setStartValue(int(start))
        self._send_press_anim.setEndValue(int(end))
        self._send_press_anim.start()

    def _send_button_pressed(self):
        if not self._sending:
            self._animate_send_icon(self.send_button.iconSize().width(), 28)

    def _send_button_released(self):
        if not self._sending:
            self._animate_send_icon(self.send_button.iconSize().width(), 36)

    def set_voice_recording(self, recording: bool, status: str = ""):
        """Reflect the dictation state without changing the draft."""
        self._voice_recording = bool(recording)
        self.voice_button.setProperty("recording", self._voice_recording)
        self.voice_button.style().unpolish(self.voice_button)
        self.voice_button.style().polish(self.voice_button)
        self.voice_button.setToolTip(status or ("Остановить запись" if recording else "Голосовой ввод"))
        if recording:
            self.message_input.hide()
            self.voice_visualizer.show()
            self.voice_visualizer.start()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            self.voice_button.setIcon(self._voice_stop_icon)
            self.voice_button.setText("")
            self.voice_button.setAccessibleName("Остановить запись")
            self._voice_glow.setEnabled(True)
            if self._voice_pulse.state() != QAbstractAnimation.State.Running:
                self._voice_pulse.start()
        else:
            self.voice_visualizer.stop()
            self.voice_visualizer.hide()
            self.message_input.show()
            self.voice_button.setText("")
            self.voice_button.setIcon(self._normal_voice_icon)
            self.voice_button.setAccessibleName("Голосовой ввод")
            self._voice_pulse.stop()
            self._voice_glow.setBlurRadius(0)
            self._voice_glow.setEnabled(False)
            self.voice_button.setIconSize(QSize(22, 22))

    def _toggle_voice_chat(self):
        if self._voice_chat_active:
            self.voice_chat_stop_requested.emit()
        else:
            self.voice_chat_requested.emit()

    def set_voice_chat_active(self, active: bool, status: str = ""):
        self._voice_chat_active = bool(active)
        self.voice_chat_button.setProperty("active", self._voice_chat_active)
        self.voice_chat_button.style().unpolish(self.voice_chat_button)
        self.voice_chat_button.style().polish(self.voice_chat_button)
        if self._voice_chat_active:
            self.voice_chat_button.setIcon(self._voice_stop_icon)
            self.voice_chat_button.setText("")
        else:
            self.voice_chat_button.setText("")
            self.voice_chat_button.setIcon(self._voice_chat_icon)
        self.voice_chat_button.setToolTip(status or ("Завершить голосовой чат" if self._voice_chat_active else "Голосовой чат в этом диалоге"))
        self.voice_button.setEnabled(not self._voice_chat_active)

    def _set_voice_icon_size(self, value):
        if self._voice_recording:
            size = max(21, min(27, int(value)))
            self.voice_button.setIconSize(QSize(size, size))

    def set_voice_level(self, level: float):
        """React to current microphone amplitude in the composer only."""
        if not self._voice_recording:
            return
        level = max(0.0, min(1.0, float(level)))
        self.voice_visualizer.set_level(level)
        self._voice_glow.setBlurRadius(8.0 + level * 28.0)
        size = int(21 + level * 7)
        self.voice_button.setIconSize(QSize(size, size))

    def insert_transcript(self, transcript: str):
        """Insert recognized text at the current cursor/selection."""
        from voice_input import merge_transcript

        cursor = self.message_input.textCursor()
        current = self.message_input.toPlainText()
        start = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        end = cursor.selectionEnd() if cursor.hasSelection() else None
        merged, new_position = merge_transcript(
            current,
            transcript,
            position=cursor.position(),
            selection_start=start,
            selection_end=end,
        )
        self.message_input.setPlainText(merged)
        cursor = self.message_input.textCursor()
        cursor.setPosition(new_position)
        self.message_input.setTextCursor(cursor)
        self.message_input.ensureCursorVisible()
        self.message_input.setFocus()

    def eventFilter(self, watched, event):
        """Match Crazy Tad composer keyboard behavior."""
        voice_targets = {self, self.message_input, self.voice_visualizer, self.voice_button}
        if watched in voice_targets and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape and self._voice_recording:
                self.voice_cancel_requested.emit()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._voice_recording:
                self.voice_requested.emit()
                return True
        if watched is self.message_input and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                if not event.modifiers():
                    self.submit()
                    return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        """Keep Enter usable even after the text editor is hidden for recording."""
        if self._voice_recording and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.voice_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def pick_files(self):
        menu = QMenu(self)
        menu.setObjectName("attachmentMenu")
        menu.setStyleSheet(
            f"QMenu#attachmentMenu {{ background: rgba(19,24,31,245); color: #f2f7fb; "
            f"border: 1px solid {self.accent}; border-radius: 10px; padding: 6px; }}"
            "QMenu#attachmentMenu::item { padding: 9px 18px 9px 10px; border-radius: 6px; }"
            f"QMenu#attachmentMenu::item:selected {{ background: {self.accent}; color: #071116; }}"
        )
        icon_root = self.asset_root / "icons" / "attachments" / "svg"
        photo_action = menu.addAction(QIcon(str(icon_root / "image.svg")), "Фото или видео")
        document_action = menu.addAction(QIcon(str(icon_root / "document.svg")), "Документ")
        music_action = menu.addAction(QIcon(str(icon_root / "audio.svg")), "Музыка")
        menu.addSeparator()
        tools_label = menu.addSection("ИНСТРУМЕНТЫ И ИНТЕГРАЦИИ")
        control_action = menu.addAction("Контроль ПК")
        browser_action = menu.addAction("Контроль браузера")
        figma_action = menu.addAction("Подключение к Figma")
        plugins_action = menu.addAction("Плагины")
        menu.adjustSize()
        anchor = self.attach_button.mapToGlobal(self.attach_button.rect().topLeft())
        chosen = menu.exec(anchor - QPoint(0, menu.sizeHint().height() + 8))
        if chosen is photo_action:
            filter_text = "Фото и видео (*.png *.jpg *.jpeg *.gif *.webp *.mp4 *.mov *.webm *.avi *.mkv)"
        elif chosen is document_action:
            filter_text = "Документы и файлы (*.*)"
        elif chosen is music_action:
            filter_text = "Аудио (*.mp3 *.wav *.flac *.ogg *.m4a *.aac)"
        else:
            tool_map = {
                control_action: "control_windows",
                browser_action: "browser",
                figma_action: "figma",
                plugins_action: "plugins",
            }
            tool = tool_map.get(chosen)
            if tool:
                self.tool_requested.emit(tool)
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Прикрепить файлы", "", filter_text)
        for path in paths:
            self.add_attachment(Path(path))

    def add_attachment(
        self, path: Path, *, kind: str = "file", pack_id: str = "", item_id: str = "",
        send_mode: str = "file", fallback: str = "",
    ):
        path = Path(path)
        # Crazy Tad deduplicates ordinary files but allows deliberately
        # repeated semantic picker items in one draft.
        duplicate = any(item.path == str(path) for item in self.pending_attachments)
        if not path.is_file() or (duplicate and kind == "file"):
            return
        if kind in {"mult", "sticker"} and send_mode == "draft_attachment":
            self._insert_inline_emote(
                path, kind=kind, pack_id=pack_id, item_id=item_id,
                send_mode=send_mode, fallback=fallback,
            )
            return
        attachment = DraftAttachment(
            path=str(path), name=path.name,
            media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            kind=kind, pack_id=pack_id, item_id=item_id,
            send_mode=send_mode,
        )
        self.pending_attachments.append(attachment)
        chip = AttachmentChip(attachment)
        chip.removed.connect(lambda item=attachment, widget=chip: self.remove_attachment(item, widget))
        self.attachments_layout.insertWidget(self.attachments_layout.count() - 1, chip)
        self.attachments_scroll.setVisible(True)
        self.attachments_scroll.setMinimumHeight(72)
        self.attachments_content.adjustSize()

    def _insert_inline_emote(
        self, path: Path, *, kind: str, pack_id: str, item_id: str,
        send_mode: str, fallback: str = "",
    ):
        """Mirror Crazy Tad's inline semantic draft behavior for Mail.Ru/GIFs."""
        if not path.is_file():
            return
        image = QImage(str(path))
        is_retro = pack_id == "telegram_retro" and path.suffix.lower() == ".json"
        if image.isNull() and not is_retro:
            return
        queue_id = f"emote_{id(path)}_{len(self.pending_attachments)}"
        resource_url = QUrl(f"jarvis-emote://{queue_id}")
        marker = QImage(28, 28, QImage.Format.Format_ARGB32)
        marker.fill(Qt.GlobalColor.transparent)
        self.message_input.document().addResource(
            QTextDocument.ResourceType.ImageResource, resource_url,
            marker if path.suffix.lower() == ".gif" or is_retro else image
        )
        image_format = QTextImageFormat()
        image_format.setName(resource_url.toString())
        image_format.setWidth(28)
        # Keep the document line metrics unchanged; the visible 28px GIF/
        # Lottie is painted by an overlay, matching Crazy Tad's composer.
        image_format.setHeight(1)
        image_format.setProperty(self._inline_emote_property, queue_id)
        cursor = QTextCursor(self._picker_cursor) if self._picker_cursor is not None else self.message_input.textCursor()
        cursor.insertImage(image_format)
        self.message_input.setTextCursor(cursor)
        self._picker_cursor = QTextCursor(cursor)
        self._inline_positions[queue_id] = cursor.position() - 1
        emote = {
            "pack_id": pack_id,
            "item_id": item_id,
            "kind": kind,
            "send_mode": send_mode,
            "name": path.name,
            "fallback": fallback or "◈",
        }
        self.pending_attachments.append(DraftAttachment(
            path=str(path), name=path.name,
            media_type=mimetypes.guess_type(path.name)[0] or "image/gif",
            kind=kind, pack_id=pack_id, item_id=item_id,
            send_mode=send_mode, emote=emote,
        ))
        if path.suffix.lower() == ".gif":
            movie = QMovie(str(path))
            movie.setCacheMode(QMovie.CacheMode.CacheAll)
            label = QLabel(self.message_input.viewport())
            label.setFixedSize(28, 28)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            label.setMovie(movie)
            movie.start()
            self._inline_emotes[queue_id] = (movie, label)
        elif is_retro:
            fallback = QLabel(fallback or "◈", self.message_input.viewport())
            fallback.setFixedSize(28, 28)
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setStyleSheet(f"color: {self.accent}; background: transparent; font-size: 20px;")
            fallback.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            fallback.show()
            self._inline_fallbacks[queue_id] = fallback
            json_path = path.resolve()
            try:
                animation = json.loads(json_path.read_text(encoding="utf-8"))
                html = """<!doctype html><html><body style='margin:0;overflow:hidden;background:transparent'><div id='lottie' style='width:28px;height:28px'></div><script src='lottie.min.js'></script><script>lottie.loadAnimation({container:document.getElementById('lottie'),renderer:'canvas',loop:true,autoplay:true,animationData:%s});</script></body></html>""" % json.dumps(animation, ensure_ascii=False)
                view = QWebEngineView(self.message_input.viewport())
                view.setFixedSize(28, 28)
                view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                view.setStyleSheet("background: transparent; border: 0;")
                view.page().setBackgroundColor(Qt.GlobalColor.transparent)
                view.setHtml(html, QUrl.fromLocalFile(str(self.asset_root / "emoji" / "")))
                self._inline_lottie[queue_id] = view
                view.show()
                view.raise_()
                QTimer.singleShot(250, view.raise_)
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                pass
        self.message_input.setFocus()
        QTimer.singleShot(0, self._reposition_inline_emotes)

    def _reposition_inline_emotes(self):
        if not self._inline_emotes and not self._inline_lottie and not self._inline_fallbacks:
            return
        cursor = QTextCursor(self.message_input.document())
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        positions: dict[str, QPoint] = {}
        while not cursor.atEnd():
            fmt = cursor.charFormat()
            object_cursor = QTextCursor(cursor)
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
            if cursor.selectedText() == "\ufffc":
                for queue_id, object_position in self._inline_positions.items():
                    if object_position != object_cursor.position():
                        continue
                    object_cursor.clearSelection()
                    cell = self.message_input.cursorRect(object_cursor)
                    top = max(0, (self.message_input.viewport().height() - 28) // 2) if cell.height() <= 1 else cell.top() + (cell.height() - 28) // 2
                    positions[str(queue_id)] = QPoint(cell.left(), top)
            cursor.clearSelection()
        for queue_id, (_movie, label) in self._inline_emotes.items():
            point = positions.get(queue_id)
            if point is None:
                label.hide()
            else:
                label.move(point)
                label.show()
        for queue_id, view in self._inline_lottie.items():
            point = positions.get(queue_id)
            if point is None:
                view.hide()
            else:
                view.move(point)
                view.show()
        for queue_id, label in self._inline_fallbacks.items():
            point = positions.get(queue_id)
            if point is None:
                label.hide()
            else:
                label.move(point)
                label.show()

    def _on_contents_change(self, position, chars_removed, chars_added):
        edit_end = position + chars_removed
        delta = chars_added - chars_removed
        updated = {}
        for queue_id, object_position in self._inline_positions.items():
            if chars_removed and position <= object_position < edit_end:
                movie_entry = self._inline_emotes.pop(queue_id, None)
                if movie_entry:
                    movie_entry[0].stop()
                    movie_entry[1].deleteLater()
                view = self._inline_lottie.pop(queue_id, None)
                if view:
                    view.deleteLater()
                fallback = self._inline_fallbacks.pop(queue_id, None)
                if fallback:
                    fallback.deleteLater()
                continue
            if object_position >= edit_end:
                object_position += delta
            updated[queue_id] = object_position
        self._inline_positions = updated

    def remove_attachment(self, attachment: DraftAttachment, widget: QWidget):
        if attachment in self.pending_attachments:
            self.pending_attachments.remove(attachment)
        widget.deleteLater()
        self.attachments_scroll.setVisible(bool(self.pending_attachments))
        if not self.pending_attachments:
            self.attachments_scroll.setMinimumHeight(0)

    def toggle_picker(self):
        if self.picker and self.picker.isVisible():
            self.picker.close()
            return
        self.picker = EmotePicker(self.asset_root, self.accent, self)
        self.picker.selected.connect(self._select_emote)
        self.picker.move(self.emote_button.mapToGlobal(self.emote_button.rect().topLeft()) - QPoint(0, 330))
        self.picker.show()

    def capture_picker_cursor(self):
        self._picker_cursor = QTextCursor(self.message_input.textCursor())

    def insert_emoji_at_picker_cursor(self, emoji: str):
        cursor = QTextCursor(self._picker_cursor) if self._picker_cursor is not None else self.message_input.textCursor()
        cursor.insertText(str(emoji))
        self.message_input.setTextCursor(cursor)
        self._picker_cursor = QTextCursor(cursor)
        self.message_input.setFocus()

    def _select_emote(self, value):
        if isinstance(value, DraftAttachment):
            self.add_attachment(
                Path(value.path), kind=value.kind, pack_id=value.pack_id,
                item_id=value.item_id, send_mode=value.send_mode,
            )
        else:
            self.message_input.insertPlainText(str(value))

    def _draft_text(self) -> str:
        """Serialize the editor while retaining inline emote object markers.

        Qt's ``QTextEdit.toPlainText()`` may omit an image object when its
        resource is transparent.  The donor composer keeps one U+FFFC marker
        per inline emote so the history renderer can place the animated media
        between surrounding text instead of rendering a separate broken-file
        grid.  Walking the document cursor preserves that contract.
        """
        cursor = QTextCursor(self.message_input.document())
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        parts: list[str] = []
        while not cursor.atEnd():
            cursor.movePosition(
                QTextCursor.MoveOperation.Right,
                QTextCursor.MoveMode.KeepAnchor,
            )
            selected = cursor.selectedText()
            parts.append("\ufffc" if selected == "\ufffc" else selected)
            cursor.clearSelection()
        value = "".join(parts).strip()
        # A media-only draft can expose no text through Qt even though the
        # object cells are present.  The attachment order is deterministic and
        # is exactly the order used by renderMessageBody().
        if not value and any(item.emote for item in self.pending_attachments):
            return "\ufffc" * sum(1 for item in self.pending_attachments if item.emote)
        return value

    def set_reply(self, message_id: str, preview: str):
        self.reply_context = {"message_id": str(message_id), "preview": preview}
        self.reply_label.setText(f"Ответ: {preview}")
        self.reply_bar.setVisible(True)

    def clear_reply(self):
        self.reply_context = None
        self.reply_bar.setVisible(False)
        self.reply_cleared.emit()

    def submit(self):
        if self._sending:
            self.cancel_requested.emit()
            return
        text = self._draft_text()
        if not text and not self.pending_attachments:
            return
        attachments = [item.to_dict() for item in self.pending_attachments]
        if self.reply_context:
            attachments = [{"reply_to": self.reply_context}, *attachments]
        self.send_requested.emit(text, attachments)
        self.message_input.clear()
        for widget in self.attachments_content.findChildren(AttachmentChip):
            widget.deleteLater()
        self.pending_attachments.clear()
        for movie, label in self._inline_emotes.values():
            movie.stop()
            label.deleteLater()
        self._inline_emotes.clear()
        for view in self._inline_lottie.values():
            view.deleteLater()
        self._inline_lottie.clear()
        for label in self._inline_fallbacks.values():
            label.deleteLater()
        self._inline_fallbacks.clear()
        self._inline_positions.clear()
        self.attachments_scroll.setVisible(False)
        self.clear_reply()

