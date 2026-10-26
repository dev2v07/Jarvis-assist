import sys
import requests
import os
import ctypes
import subprocess
import webbrowser
import json
import winsound

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from PySide6.QtSvgWidgets import QSvgWidget
from toggle_switch import ToggleSwitch
from jarvis_hud import JarvisHUD

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

print(os.path.join(BASE_DIR, "assets", "jarvis_off.png"))

API_URL = "http://127.0.0.1:8000/chat"
STARTUP_DIAGNOSTIC_WAV = os.path.abspath(os.path.join(
    BASE_DIR, "..", "backend", "voice_engine", "sound",
    "Начинаю диагностику системы (второй).wav"
))

TECH_FONT_FILES = {
    "Good Times": "GOODTIME.ttf",
    "Imagine font": "imagine_font.ttf",
    "HandelGotD": "HandelGotD.ttf",
    "Nasalization": "nasaliza.ttf",
    "BitDust Two": "bitdust2.ttf",
}

TECH_ACTION_BUTTONS = {
    "COMP": (137, 227),
    "DOCS": (124, 281),
    "CTRL": (124, 340),
    "DESK": (127, 393),
    "XPLR": (536, 233),
    "CHRM": (556, 288),
    "GAME": (560, 348),
    "CFG": (545, 399),
}

HUD_TOP_PANEL_BUTTONS = {
    "CHAT": (266, 137),
    "AGENTS": (333, 137),
    "FUNCTION": (407, 137),
    "HISTORY": (493, 137),
}

HUD_BOTTOM_PANEL_BUTTONS = {
    "PROV": (232, 548),
    "MOD": (291, 548),
    "VID": (350, 548),
    "SET": (409, 548),
    "OUT": (468, 548),
}

WIDGET_ACTION_OPTIONS = [
    "CHAT", "AGENTS", "FUNCTION", "HISTORY", "PROV", "MOD", "VID", "SET", "OUT",
]
PANEL_ASSIGNMENT_KEYS = list(HUD_TOP_PANEL_BUTTONS) + list(HUD_BOTTOM_PANEL_BUTTONS) + list(TECH_ACTION_BUTTONS)
PANEL_ASSIGNMENT_OPTIONS = WIDGET_ACTION_OPTIONS + list(TECH_ACTION_BUTTONS) + ["CUSTOM"]
TIME_FORMAT_OPTIONS = (
    ("24 часа — 14:30", "%H:%M"),
    ("24 часа с секундами — 14:30:25", "%H:%M:%S"),
    ("12 часов — 02:30 PM", "%I:%M %p"),
)
DATE_FORMAT_OPTIONS = (
    ("TECH-A — 25TH OCT", "ORDINAL"),
    ("25 OCT 2026", "%d %b %Y"),
    ("25.10.2026", "%d.%m.%Y"),
    ("2026-10-25", "%Y-%m-%d"),
)


class WidgetSettingsDialog(QDialog):
    """Standalone HUD settings: layers, metrics and panel assignments."""

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("НАСТРОЙКИ ВИДЖЕТА")
        self.setModal(False)
        self.resize(820, 760)
        self.settings = settings
        self.layer_checks = {}
        self.metric_checks = {}
        self.action_combos = {}
        self.target_edits = {}
        self.motion_spins = {}

        root = QVBoxLayout(self)
        title = QLabel("НАСТРОЙКИ ВИДЖЕТА TECH-A")
        title.setObjectName("settingsTitle")
        root.addWidget(title)
        hint = QLabel("Слои, метрики и назначения кнопок сохраняются отдельно от общих настроек приложения.")
        hint.setObjectName("settingsHint")
        root.addWidget(hint)

        content = QHBoxLayout()
        layers_box = QGroupBox("СЛОИ")
        layers_box.setObjectName("settingsTile")
        layers_layout = QVBoxLayout(layers_box)
        layer_values = settings.get("layers", {})
        for name in ("BG1", "BG2/BG000", "BG3", "BG4", "BG5", "BG6", "ROTATOR 1", "ROTATOR 2"):
            check = QCheckBox(name)
            check.setChecked(layer_values.get(name, True))
            self.layer_checks[name] = check
            layers_layout.addWidget(check)
        content.addWidget(layers_box)

        metrics_box = QGroupBox("МЕТРИКИ")
        metrics_box.setObjectName("settingsTile")
        metrics_layout = QVBoxLayout(metrics_box)
        metric_values = settings.get("metrics", {})
        for name in ("CPU", "RAM", "GPU", "DISK"):
            check = QCheckBox(name)
            check.setChecked(metric_values.get(name, True))
            self.metric_checks[name] = check
            metrics_layout.addWidget(check)
        metrics_layout.addStretch()
        content.addWidget(metrics_box)
        root.addLayout(content)

        motion_box = QGroupBox("АНИМАЦИЯ И РАЗМЕРЫ")
        motion_box.setObjectName("settingsTile")
        motion_layout = QFormLayout(motion_box)
        motion_values = settings.get("motion", {})
        motion_fields = (
            ("ROTATOR 1 — размер (%)", "rotator_1_size", 100, 25, 200),
            ("ROTATOR 1 — оборот (сек.)", "rotator_1_seconds", 75, 1, 600),
            ("ROTATOR 2 — размер (%)", "rotator_2_size", 100, 25, 200),
            ("ROTATOR 2 — оборот (сек.)", "rotator_2_seconds", 125, 1, 600),
            ("BG000 — размер (%)", "bg000_size", 100, 25, 200),
            ("BG000 — оборот (сек.)", "bg000_seconds", 40, 1, 600),
        )
        for label, key, fallback, minimum, maximum in motion_fields:
            spin = QSpinBox()
            spin.setRange(minimum, maximum)
            spin.setValue(int(motion_values.get(key, fallback)))
            spin.setSuffix(" %" if "size" in key else " сек")
            self.motion_spins[key] = spin
            motion_layout.addRow(QLabel(label), spin)
        root.addWidget(motion_box)

        datetime_box = QGroupBox("ВРЕМЯ И ДАТА HUD")
        datetime_box.setObjectName("settingsTile")
        datetime_layout = QFormLayout(datetime_box)
        datetime_values = settings.get("datetime", {})
        self.time_format_combo = QComboBox()
        for label, value in TIME_FORMAT_OPTIONS:
            self.time_format_combo.addItem(label, value)
        self.time_format_combo.setCurrentIndex(max(
            0, self.time_format_combo.findData(datetime_values.get("time_format", "%H:%M"))
        ))
        datetime_layout.addRow(QLabel("Формат времени"), self.time_format_combo)
        self.time_size_spin = QSpinBox()
        self.time_size_spin.setRange(6, 48)
        self.time_size_spin.setSuffix(" px")
        self.time_size_spin.setValue(int(datetime_values.get("time_size", 14)))
        datetime_layout.addRow(QLabel("Размер времени"), self.time_size_spin)
        self.date_format_combo = QComboBox()
        for label, value in DATE_FORMAT_OPTIONS:
            self.date_format_combo.addItem(label, value)
        self.date_format_combo.setCurrentIndex(max(
            0, self.date_format_combo.findData(datetime_values.get("date_format", "ORDINAL"))
        ))
        datetime_layout.addRow(QLabel("Формат даты"), self.date_format_combo)
        self.date_size_spin = QSpinBox()
        self.date_size_spin.setRange(6, 36)
        self.date_size_spin.setSuffix(" px")
        self.date_size_spin.setValue(int(datetime_values.get("date_size", 8)))
        datetime_layout.addRow(QLabel("Размер даты"), self.date_size_spin)
        root.addWidget(datetime_box)

        assignments = QGroupBox("НАЗНАЧЕНИЕ ПАНЕЛЕЙ")
        assignments.setObjectName("settingsTile")
        assignments_layout = QFormLayout(assignments)
        action_values = settings.get("actions", {})
        target_values = settings.get("targets", {})
        for key in PANEL_ASSIGNMENT_KEYS:
            combo = QComboBox()
            combo.addItems(PANEL_ASSIGNMENT_OPTIONS)
            combo.setCurrentText(action_values.get(key, key))
            self.action_combos[key] = combo
            target = QLineEdit(target_values.get(key, ""))
            target.setPlaceholderText("EXE, папка или URL — для CUSTOM")
            self.target_edits[key] = target
            row = QHBoxLayout()
            row.addWidget(combo, 1)
            row.addWidget(target, 2)
            assignments_layout.addRow(QLabel(key), row)
        assignment_scroll = QScrollArea()
        assignment_scroll.setWidgetResizable(True)
        assignment_scroll.setFrameShape(QFrame.NoFrame)
        assignment_scroll.setWidget(assignments)
        root.addWidget(assignment_scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("СОХРАНИТЬ")
        buttons.button(QDialogButtonBox.Cancel).setText("ОТМЕНА")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self):
        return {
            "layers": {name: check.isChecked() for name, check in self.layer_checks.items()},
            "metrics": {name: check.isChecked() for name, check in self.metric_checks.items()},
            "actions": {name: combo.currentText() for name, combo in self.action_combos.items()},
            "targets": {name: edit.text().strip() for name, edit in self.target_edits.items()},
            "motion": {name: spin.value() for name, spin in self.motion_spins.items()},
            "datetime": {
                "time_format": self.time_format_combo.currentData(),
                "time_size": self.time_size_spin.value(),
                "date_format": self.date_format_combo.currentData(),
                "date_size": self.date_size_spin.value(),
            },
            "panel_positions": self.settings.get("panel_positions", {}),
        }


class RotatablePanelButton(QPushButton):
    """Text panel button whose label can be tilted without rotating its hitbox."""

    angleChanged = Signal(float)

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.panel_angle = 0.0

    def set_panel_angle(self, angle):
        self.panel_angle = max(-45.0, min(45.0, float(angle)))
        self.update()

    def wheelEvent(self, event):
        if self.property("calibrationEnabled"):
            step = 2 if event.angleDelta().y() > 0 else -2
            self.set_panel_angle(self.panel_angle + step)
            self.angleChanged.emit(self.panel_angle)
            event.accept()
            return
        super().wheelEvent(event)

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        text = option.text
        option.text = ""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, self)

        painter.translate(self.rect().center())
        painter.rotate(self.panel_angle)
        painter.setPen(QColor(self.property("panelTextColor") or "#ffffff"))
        painter.setFont(self.font())
        painter.drawText(
            QRectF(-self.width() / 2, -self.height() / 2, self.width(), self.height()),
            Qt.AlignmentFlag.AlignCenter,
            text,
        )
        painter.end()


# ---------------- MESSAGE BUBBLE ----------------

class MessageBubble(QWidget):

    def __init__(self, text, user):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.label = QLabel(text)
        self.label.setMaximumWidth(120)
        self.label.setWordWrap(False)
        self.label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.label.setStyleSheet("""
        color:white;
        font-size:13px;
        """)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(800)
        self.label.adjustSize()

        self.label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        

        if user:

            self.label.setStyleSheet("""
            QLabel{
                background:#EAEAEA;
                color:black;
                padding:8px 14px;
                border-radius:14px 14px 4px 14px;
            }
            """)

            layout.addStretch()
            layout.addWidget(self.label)

        else:

            self.label.setStyleSheet("""
            QLabel{
                background:#2E89FF;
                color:white;
                padding:8px 14px;
                border-radius:14px 14px 14px 4px;
            }
            """)

            layout.addWidget(self.label)
            layout.addStretch()

        # анимация появления
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(200)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()

# ---------------- CHAT ITEM WIDGET ----------------

class ChatItemWidget(QWidget):

    def __init__(self, text, pinned=False):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8,4,8,4)
        layout.setSpacing(6)

        self.label = QLabel(text)
        self.label.setStyleSheet("color:white;font-size:13px;")

        self.pin = QLabel()
        self.pin.setFixedSize(12,12)

        if pinned:
            pin_path = os.path.join(BASE_DIR,"assets","pin.svg")
            self.pin.setPixmap(QIcon(pin_path).pixmap(12,12))

        self.menu_btn = QPushButton("⋯")
        self.menu_btn.setFixedSize(18,18)
        self.menu_btn.hide()

        self.menu_btn.setStyleSheet("""
        QPushButton{
            background:transparent;
            border:none;
            color:#aaa;
        }
        QPushButton:hover{
            color:white;
        }
        """)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.pin)
        layout.addWidget(self.menu_btn)


# ---------------- TECH-A BUTTON ----------------

class TechActionButton(QToolButton):
    """Rainmeter-like three-state sprite button without a Qt hover overlay."""

    def __init__(self, static_frame, hover_frame, pressed_frame, parent=None):
        super().__init__(parent)
        self.static_frame = static_frame
        self.hover_frame = hover_frame
        self.pressed_frame = pressed_frame
        self.setIcon(QIcon(self.static_frame))
        self.setIconSize(self.static_frame.size())
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self.setIcon(QIcon(self.hover_frame))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(QIcon(self.static_frame))
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.setIcon(QIcon(self.pressed_frame))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setIcon(QIcon(self.hover_frame if self.underMouse() else self.static_frame))


class StartButton(QPushButton):
    """START button with a restrained readable shadow and accent contour."""

    def __init__(self, text, text_color, accent_color, parent=None):
        super().__init__(text, parent)
        self.start_text_color = QColor(text_color)
        self.start_accent_color = QColor(accent_color)
        self.start_hovered = False

    def set_text_color(self, color):
        parsed = QColor(color)
        if parsed.isValid():
            self.start_text_color = parsed
            self.update()

    def set_accent_color(self, color):
        parsed = QColor(color)
        if parsed.isValid():
            self.start_accent_color = parsed
            self.update()

    def enterEvent(self, event):
        self.start_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.start_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        option = QStyleOptionButton()
        self.initStyleOption(option)
        text = option.text
        option.text = ""
        self.style().drawControl(QStyle.CE_PushButton, option, painter, self)

        painter.setFont(self.font())
        text_rect = self.rect()

        # Dark offset shadow keeps START readable over the bright glass core.
        shadow = QColor(0, 0, 0, 225 if self.start_hovered else 210)
        painter.setPen(shadow)
        painter.drawText(
            text_rect.translated(0, 3 if self.start_hovered else 2),
            Qt.AlignCenter,
            text,
        )

        # A restrained accent contour adds separation without a heavy glow.
        contour = QColor(self.start_accent_color)
        contour.setAlpha(180 if self.start_hovered else 115)
        painter.setPen(contour)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            painter.drawText(text_rect.translated(dx, dy), Qt.AlignCenter, text)

        painter.setPen(self.start_text_color)
        painter.drawText(text_rect, Qt.AlignCenter, text)


# ---------------- MAIN UI ----------------

class JarvisUI(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Jarvis Assist")
        self.resize(1280, 850)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.ui_settings = QSettings("Jarvis", "Jarvis Assist")
        self.visual_settings = {
            "window_opacity": int(self.ui_settings.value("window_opacity", 96)),
            "transparent_background": self.ui_settings.value(
                "transparent_background", True, type=bool
            ),
            "glass_enabled": self.ui_settings.value("glass_enabled", True, type=bool),
        }
        self.hardware_settings = {
            "audio_input_device": int(self.ui_settings.value("audio_input_device", -1)),
            "video_input_device": int(self.ui_settings.value("video_input_device", 0)),
        }
        self.startup_widget_mode = self.ui_settings.value("startup_widget_mode", True, type=bool)
        self.setAttribute(
            Qt.WA_TranslucentBackground,
            self.visual_settings["transparent_background"],
        )
        self.widget_settings = self.load_widget_settings()
        self.panel_calibration_mode = "--calibrate-panels" in sys.argv
        self._panel_drag = None
        self.tech_font_families = self.register_tech_fonts()
        self.active_font_family = self.ui_settings.value(
            "font_family",
            self.tech_font_families.get("Good Times", "Arial"),
        )
        stored_accent = self.ui_settings.value("accent_color", "#00ebf5")
        self.accent_color = QColor(stored_accent)
        if not self.accent_color.isValid():
            self.accent_color = QColor("#00ebf5")
        self.accent_hex = self.accent_color.name()
        stored_text_color = self.ui_settings.value("font_color", "#ffffff")
        self.text_color = QColor(stored_text_color)
        if not self.text_color.isValid():
            self.text_color = QColor("#ffffff")
        self.text_color_hex = self.text_color.name()
        QApplication.instance().setFont(QFont(self.active_font_family, 10))

        self.oldPos = None
        self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)

        self.build_ui()
        self.apply_application_font()
        QTimer.singleShot(900, self.play_startup_diagnostic)

        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)
        if self.startup_widget_mode:
            QTimer.singleShot(0, self.toggle_widget_mode)

        self.load_weather()

        if self.panel_calibration_mode:
            self.assistant_label.setText("КАЛИБРОВКА ПАНЕЛЕЙ: перетащите иконки мышью")

        self.weather_timer = QTimer()
        self.weather_timer.timeout.connect(self.load_weather)
        self.weather_timer.start(600000)

        # hover отслеживание
        self.chats_list.setMouseTracking(True)
        self.chats_list.viewport().setMouseTracking(True)
        self.chats_list.viewport().installEventFilter(self)

    def play_startup_diagnostic(self):
        """Play the optional local startup phrase without blocking the UI."""
        enabled = self.ui_settings.value("startup_diagnostic_enabled", True, type=bool)
        if enabled and os.path.isfile(STARTUP_DIAGNOSTIC_WAV):
            winsound.PlaySound(
                STARTUP_DIAGNOSTIC_WAV,
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )

    def load_widget_settings(self):
        default = {
            "layers": {
                "BG1": True, "BG2/BG000": True, "BG3": True, "BG4": True,
                "BG5": True, "BG6": True, "ROTATOR 1": True, "ROTATOR 2": True,
            },
            "metrics": {"CPU": True, "RAM": True, "GPU": True, "DISK": True},
            "actions": {key: key for key in PANEL_ASSIGNMENT_KEYS},
            "targets": {},
            "motion": {
                "rotator_1_size": 100, "rotator_2_size": 100, "bg000_size": 100,
                "rotator_1_seconds": 75, "rotator_2_seconds": 125, "bg000_seconds": 40,
            },
            "datetime": {
                "time_format": "%H:%M", "time_size": 14,
                "date_format": "ORDINAL", "date_size": 8,
            },
            "panel_positions": {
                key: {"x": position[0], "y": position[1], "angle": 0}
                for key, position in {**HUD_TOP_PANEL_BUTTONS, **HUD_BOTTOM_PANEL_BUTTONS}.items()
            },
        }
        raw = self.ui_settings.value("widget_settings", "")
        if not raw:
            return default
        try:
            saved = json.loads(raw)
            for group in ("layers", "metrics", "actions", "targets", "motion", "datetime"):
                default[group].update(saved.get(group, {}))
            default["panel_positions"].update(saved.get("panel_positions", {}))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        return default

    def open_widget_settings(self):
        dialog = WidgetSettingsDialog(self, self.widget_settings)
        dialog.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        dialog.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        dialog.setStyleSheet(self.dialog_stylesheet())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.widget_settings = dialog.values()
            self.ui_settings.setValue("widget_settings", json.dumps(self.widget_settings, ensure_ascii=False))
            self.hud.apply_widget_settings(self.widget_settings)
            self.hud.set_datetime_settings(self.widget_settings.get("datetime", {}))
            for key, button in getattr(self, "hud_panel_button_map", {}).items():
                button.setProperty("actionKey", self.widget_settings["actions"].get(key, key))
                button.style().unpolish(button)
                button.style().polish(button)
            self.assistant_label.setText("Настройки виджета сохранены")

    def open_custom_target(self, target, source_name=None):
        """Open a user-defined URL, application or folder from a panel binding."""
        if not target:
            self.assistant_label.setText(f"Для {source_name or 'кнопки'} не задан адрес")
            return
        try:
            if target.lower().startswith(("http://", "https://", "mailto:")):
                webbrowser.open(target)
            elif os.path.exists(target):
                os.startfile(target)
            else:
                subprocess.Popen(target, shell=True)
            self.assistant_label.setText(f"Открыто: {target}")
        except (OSError, ValueError) as error:
            self.assistant_label.setText(f"Не удалось открыть {target}: {error}")


    def activate_assistant(self):

     self.jarvis_state = not self.jarvis_state

     if self.jarvis_state:
        self.jarvis_button.setText("STOP")
        self.jarvis_button.setProperty("active", True)
        self.jarvis_button.style().unpolish(self.jarvis_button)
        self.jarvis_button.style().polish(self.jarvis_button)

        self.assistant_label.setText("JARVIS слушает...")

        # запускаем пульс
        self.pulse_anim.start()

        print("Jarvis ON")

     else:
        self.jarvis_button.setText("START")
        self.jarvis_button.setProperty("active", False)
        self.jarvis_button.style().unpolish(self.jarvis_button)
        self.jarvis_button.style().polish(self.jarvis_button)

        self.assistant_label.setText("Нажмите кнопку чтобы активировать JARVIS")

        # выключаем пульс
        self.pulse_anim.stop()
        self.glow.setBlurRadius(40)

        print("Jarvis OFF")

    def create_tech_action_buttons(self, parent):
        """Restore the eight clickable TECH-A image buttons from the Rainmeter skin."""
        assets_dir = os.path.join(BASE_DIR, "assets", "TECH-A")
        buttons = []

        for name, (x, y) in TECH_ACTION_BUTTONS.items():
            path = os.path.join(assets_dir, f"{name}.png")
            sprite = QPixmap(path)
            if sprite.isNull() or sprite.width() % 3:
                continue

            # TECH-A stores three horizontal states in one PNG:
            # static | hover | pressed. Do not render the complete sprite.
            frame_width = sprite.width() // 3
            static_frame = sprite.copy(0, 0, frame_width, sprite.height())
            # Rainmeter order is UP | DOWN | OVER, not UP | OVER | DOWN.
            pressed_frame = sprite.copy(frame_width, 0, frame_width, sprite.height())
            hover_frame = sprite.copy(frame_width * 2, 0, frame_width, sprite.height())

            button = TechActionButton(static_frame, hover_frame, pressed_frame, parent)
            button.setObjectName("techTool")
            button.setGeometry(x, y, frame_width, sprite.height())
            button.setToolTip(name)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, key=name: self.handle_tech_action(key))
            button.show()
            button.raise_()
            buttons.append(button)

        return buttons

    def create_hud_panel_buttons(self, parent):
        """Create the upper command labels and lower SVG command icons."""
        buttons = []
        self.hud_panel_button_map = {}
        action_map = self.widget_settings.get("actions", {})
        position_map = self.widget_settings.get("panel_positions", {})
        for name, (x, y) in HUD_TOP_PANEL_BUTTONS.items():
            saved_position = position_map.get(name, {"x": x, "y": y})
            x, y = saved_position.get("x", x), saved_position.get("y", y)
            button = RotatablePanelButton(name, parent)
            button.setObjectName("hudPanelTop")
            button.setProperty("actionKey", action_map.get(name, name))
            button.setProperty("panelName", name)
            button.setProperty("panelTextColor", self.text_color_hex)
            button.set_panel_angle(saved_position.get("angle", 0))
            button.setGeometry(x, y, 72 if name != "FUNCTION" else 86, 24)
            button.setCursor(Qt.PointingHandCursor)
            if self.panel_calibration_mode:
                button.setProperty("calibrationEnabled", True)
                button.setToolTip(f"{name}: перетащите мышью, колесо — наклон текста")
                button.installEventFilter(self)
                button.angleChanged.connect(lambda angle, item=button: self.save_panel_position(item))
            button.clicked.connect(lambda checked=False, item=button: self.handle_hud_panel_action(
                item.property("actionKey"), item.property("panelName")
            ))
            button.show()
            button.raise_()
            buttons.append(button)
            self.hud_panel_button_map[name] = button

        icons_dir = os.path.join(BASE_DIR, "assets", "TECH-A", "panel")
        for name, (x, y) in HUD_BOTTOM_PANEL_BUTTONS.items():
            saved_position = position_map.get(name, {"x": x, "y": y})
            x, y = saved_position.get("x", x), saved_position.get("y", y)
            button = QToolButton(parent)
            button.setObjectName("hudPanelIcon")
            button.setProperty("actionKey", action_map.get(name, name))
            button.setProperty("panelName", name)
            button.setGeometry(x, y, 40, 32)
            button.setIcon(QIcon(os.path.join(icons_dir, f"{name}.svg")))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(name)
            button.setCursor(Qt.PointingHandCursor)
            if self.panel_calibration_mode:
                button.setToolTip(f"{name}: перетащите мышью")
                button.installEventFilter(self)
            button.clicked.connect(lambda checked=False, item=button: self.handle_hud_panel_action(
                item.property("actionKey"), item.property("panelName")
            ))
            button.show()
            button.raise_()
            buttons.append(button)
            self.hud_panel_button_map[name] = button
        return buttons

    def ensure_full_ui(self):
        """Restore the normal Jarvis chrome before opening an application page."""
        if not getattr(self, "widget_mode", False):
            return
        self.widget_mode = False
        for widget in getattr(self, "widget_chrome_widgets", []):
            widget.setVisible(True)
        self.main_container.setStyleSheet("")
        self.apply_styles()

    def handle_hud_panel_action(self, name, source_key=None):
        """Route the new top/bottom HUD panel commands."""
        if name in {"CHAT", "HISTORY"}:
            self.ensure_full_ui()
        if name == "CUSTOM":
            self.open_custom_target(self.widget_settings.get("targets", {}).get(source_key, ""), source_key)
        elif name in TECH_ACTION_BUTTONS:
            self.handle_tech_action(name)
        elif name == "CHAT":
            self.menu.setCurrentRow(1)
            self.pages.setCurrentIndex(1)
        elif name == "HISTORY":
            self.menu.setCurrentRow(2)
            self.pages.setCurrentIndex(2)
        elif name == "SET":
            self.open_widget_settings()
        elif name == "AGENTS":
            self.show_panel_dialog("ДОСТУПНЫЕ АГЕНТЫ", [
                "Main Agent", "Planner", "Executor", "Critic", "File",
                "Network", "Web", "Vision", "Memory", "Performance",
                "Game Coach", "Social", "Policy", "Selfcheck",
            ])
        elif name == "FUNCTION":
            self.show_panel_dialog("ФУНКЦИИ JARVIS", [
                "Голосовое управление", "Чаты и история", "Системные команды",
                "Провайдеры и AI-модели", "Видео / видение", "Режимы TECH-A",
            ])
        elif name == "PROV":
            self.show_panel_dialog("ПРОВАЙДЕРЫ", [
                "Ollama", "Codex", "Claude", "FreeLLMAPI",
            ])
        elif name == "MOD":
            self.show_panel_dialog("МОДЕЛИ AI", [
                "Ollama — локальные модели", "Codex", "Claude", "FreeLLMAPI",
            ])
        elif name == "VID":
            self.toggle_widget_mode()
        elif name == "OUT":
            self.close()

        self.assistant_label.setText(name)

    def show_panel_dialog(self, title, items):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(False)
        dialog.resize(360, 280)
        dialog.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        dialog.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        dialog.setStyleSheet(self.dialog_stylesheet())
        layout = QVBoxLayout(dialog)
        heading = QLabel(title)
        heading.setObjectName("settingsTitle")
        layout.addWidget(heading)
        for item in items:
            label = QLabel(f"• {item}")
            label.setObjectName("settingsHint")
            layout.addWidget(label)
        close_button = QPushButton("ЗАКРЫТЬ")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        dialog.show()
        self._panel_dialog = dialog

    def dialog_stylesheet(self):
        accent_hover = self.accent_color.lighter(120).name()
        if self.visual_settings["glass_enabled"]:
            popup_background = (
                "qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                "stop:0 rgba(20,20,25,220),stop:0.35 rgba(15,15,20,220),"
                "stop:0.65 rgba(10,10,15,230),stop:1 rgba(30,30,35,220))"
            )
        else:
            popup_background = "rgba(15,15,20,220)"
        return f"""
            QDialog {{ background: {popup_background}; color: {self.text_color_hex};
                border: 1px solid rgba(255,255,255,55); border-radius: 16px; }}
            QLabel, QGroupBox, QCheckBox, QRadioButton {{ color: {self.text_color_hex}; }}
            QGroupBox, QGroupBox#settingsTile {{ border: 1px solid rgba(255,255,255,55); border-radius: 12px;
                margin-top: 10px; padding: 14px 8px 8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px;
                color: {self.accent_hex}; }}
            QPushButton, QDialogButtonBox QPushButton {{ background: {self.accent_hex};
                color: #071116; border: none; border-radius: 9px; padding: 8px 18px;
                min-height: 18px; }}
            QPushButton:hover, QDialogButtonBox QPushButton:hover {{ background: {accent_hover}; }}
            QComboBox, QLineEdit, QSpinBox {{ background: rgba(255,255,255,225); color: #111820;
                border: 1px solid rgba(255,255,255,100); border-radius: 7px; padding: 5px; }}
            QComboBox QAbstractItemView {{ background: #171b24; color: #ffffff;
                selection-background-color: {self.accent_hex}; selection-color: #071116; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
                border: 1px solid rgba(255,255,255,100); background: rgba(255,255,255,25); }}
            QCheckBox::indicator:checked {{ background: {self.accent_hex}; border: 1px solid {self.accent_hex}; }}
        """

    def toggle_widget_mode(self):
        """Toggle a transparent HUD-only presentation while keeping voice ready."""
        self.widget_mode = not getattr(self, "widget_mode", False)
        for widget in getattr(self, "widget_chrome_widgets", []):
            widget.setVisible(not self.widget_mode)
        if self.widget_mode:
            self.main_container.setStyleSheet(
                "QFrame#container { background: transparent; border: none; }"
            )
            self.setWindowOpacity(1.0)
            self.pages.setCurrentIndex(0)
        else:
            self.main_container.setStyleSheet("")
            self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
            self.apply_styles()

    def handle_tech_action(self, name):
        """Execute the portable equivalent of each original TECH-A action."""
        try:
            if name == "CFG":
                self.ensure_full_ui()
            bound_name = self.widget_settings.get("actions", {}).get(name, name)
            if bound_name == "CUSTOM":
                self.open_custom_target(self.widget_settings.get("targets", {}).get(name, ""), name)
                return
            if bound_name in TECH_ACTION_BUTTONS and bound_name != name:
                name = bound_name
            if name == "COMP":
                os.startfile("shell:MyComputerFolder")
                message = "Открыт Этот компьютер"
            elif name == "DOCS":
                os.startfile(os.path.join(os.path.expanduser("~"), "Documents"))
                message = "Открыты Документы"
            elif name == "CTRL":
                os.startfile("ms-settings:")
                message = "Открыты Параметры Windows"
            elif name == "DESK":
                self.show_desktop()
                message = "Показан рабочий стол"
            elif name == "XPLR":
                enabled = self.hud.animation.toggle_big_animation()
                message = f"ANI {'ON' if enabled else 'OFF'}"
            elif name == "CHRM":
                browser = self.open_chrome()
                message = f"Открыт {browser}"
            elif name == "GAME":
                game_mode = self.hud.animation.toggle_game_mode()
                message = "GAME MODE" if game_mode else "DESK MODE"
            elif name == "CFG":
                self.menu.setCurrentRow(3)
                message = "Открыты настройки Jarvis"
            else:
                message = f"TECH-A: {name}"
            self.assistant_label.setText(message)
            print(f"TECH-A action: {name} -> {message}")
        except OSError as error:
            message = f"Не удалось выполнить {name}: {error}"
            self.assistant_label.setText(message)
            print(message)

    @staticmethod
    def open_chrome():
        chrome_candidates = [
            os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
        for chrome_path in chrome_candidates:
            if chrome_path and os.path.isfile(chrome_path):
                subprocess.Popen([chrome_path, "--new-window"])
                return "Chrome"
        webbrowser.open("about:blank")
        return "браузер по умолчанию"

    @staticmethod
    def show_desktop():
        try:
            import win32com.client
            win32com.client.Dispatch("Shell.Application").ToggleDesktop()
        except Exception:
            # Fallback for systems without the pywin32 COM wrapper.
            user32 = ctypes.windll.user32
            user32.keybd_event(0x5B, 0, 0, 0)
            user32.keybd_event(0x44, 0, 0, 0)
            user32.keybd_event(0x44, 0, 2, 0)
            user32.keybd_event(0x5B, 0, 2, 0)

    def register_tech_fonts(self):
        families = {}
        font_dir = os.path.join(BASE_DIR, "assets", "fonts")

        for label, filename in TECH_FONT_FILES.items():
            path = os.path.join(font_dir, filename)
            font_id = QFontDatabase.addApplicationFont(path)
            loaded = QFontDatabase.applicationFontFamilies(font_id)
            if loaded:
                families[label] = loaded[0]

        return families

    def apply_font_family(self, label):
        family = self.tech_font_families.get(label)
        if not family:
            return

        self.active_font_family = family
        self.ui_settings.setValue("font_family", family)
        self.apply_application_font()
        if hasattr(self, "hud"):
            self.hud.set_interface_font(family)

    def apply_application_font(self):
        """Force the selected family onto existing and future Qt widgets."""
        font = QFont(self.active_font_family, 10)
        QApplication.instance().setFont(font)
        for widget in self.findChildren(QWidget):
            widget_font = widget.font()
            widget_font.setFamily(self.active_font_family)
            widget.setFont(widget_font)

    def container_visual_stylesheet(self):
        if self.visual_settings["glass_enabled"]:
            background = (
                "qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                "stop:0 rgba(20,20,25,220),stop:0.35 rgba(15,15,20,220),"
                "stop:0.65 rgba(10,10,15,230),stop:1 rgba(30,30,35,220))"
            )
        else:
            background = "rgba(15,15,20,220)"
        return (
            "QFrame#container { border-radius:30px; "
            f"background:{background}; border:1px solid rgba(255,255,255,40); }}"
        )

    def apply_visual_settings(self):
        """Apply the existing main-window glass parameters to every popup."""
        if hasattr(self, "transparent_background_check"):
            self.visual_settings["transparent_background"] = self.transparent_background_check.isChecked()
            self.visual_settings["glass_enabled"] = self.glass_enabled_check.isChecked()
            self.visual_settings["window_opacity"] = self.window_opacity_spin.value()
        for key, value in self.visual_settings.items():
            self.ui_settings.setValue(key, value)
        self.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        if hasattr(self, "main_container") and not getattr(self, "widget_mode", False):
            self.main_container.setStyleSheet(self.container_visual_stylesheet())
        if hasattr(self, "main_container"):
            self.apply_styles()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog):
                widget.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
                widget.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
                widget.setStyleSheet(self.dialog_stylesheet())

    def apply_datetime_settings(self):
        """Persist and apply the general clock/date presentation settings."""
        self.datetime_settings = {
            "time_format": self.time_format_combo.currentData(),
            "date_format": self.date_format_combo.currentData(),
            "time_size": self.time_size_spin.value(),
            "date_size": self.date_size_spin.value(),
        }
        for key, value in self.datetime_settings.items():
            self.ui_settings.setValue(key, value)
        if hasattr(self, "hud"):
            self.hud.set_datetime_settings(self.datetime_settings)

    def set_startup_diagnostic_enabled(self, enabled):
        self.ui_settings.setValue("startup_diagnostic_enabled", bool(enabled))

    def set_startup_widget_mode(self, enabled):
        self.startup_widget_mode = bool(enabled)
        self.ui_settings.setValue("startup_widget_mode", self.startup_widget_mode)

    @staticmethod
    def enumerate_audio_sources():
        sources = [("Системный выбор", -1)]
        try:
            import sounddevice as sd
            for index, device in enumerate(sd.query_devices()):
                if device.get("max_input_channels", 0) > 0:
                    sources.append((f"{index}: {device['name']}", index))
        except Exception as error:
            print(f"Audio device enumeration failed: {error}")
        return sources

    @staticmethod
    def enumerate_video_sources():
        sources = []
        try:
            import cv2
            for index in range(6):
                capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                opened = capture.isOpened()
                capture.release()
                if opened:
                    sources.append((f"Камера {index}", index))
        except Exception as error:
            print(f"Video device enumeration failed: {error}")
        return sources or [("Камера по умолчанию (0)", 0)]

    def apply_hardware_settings(self):
        self.hardware_settings = {
            "audio_input_device": self.audio_source_combo.currentData(),
            "video_input_device": self.video_source_combo.currentData(),
        }
        for key, value in self.hardware_settings.items():
            self.ui_settings.setValue(key, value)
        try:
            requests.post(
                "http://127.0.0.1:8000/hardware/settings",
                json=self.hardware_settings,
                timeout=2,
            )
        except requests.RequestException:
            print("Hardware settings saved locally; backend is unavailable")

    def pick_color(self, initial, title):
        dialog = QColorDialog(initial, self)
        dialog.setWindowTitle(title)
        dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        dialog.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        dialog.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        dialog.setStyleSheet("""
            QColorDialog, QDialog { background:#171922; color:#F4F7FA; }
            QColorDialog QLabel, QDialog QLabel { color:#F4F7FA; }
            QColorDialog QSpinBox, QColorDialog QLineEdit {
                background:#252A36; color:#F4F7FA; border:1px solid #4A5263;
                border-radius:5px; padding:3px;
            }
            QColorDialog QPushButton {
                background:#27303D; color:#F4F7FA; border:1px solid #566176;
                border-radius:6px; padding:6px 14px;
            }
            QColorDialog QPushButton:hover { background:#3A4658; }
        """)
        return dialog.currentColor() if dialog.exec() == QDialog.Accepted else QColor()

    def choose_accent_color(self):
        color = self.pick_color(self.accent_color, "Выберите акцентный цвет")
        if not color.isValid():
            return

        self.accent_color = color
        self.accent_hex = color.name()
        self.ui_settings.setValue("accent_color", self.accent_hex)
        self.hud.set_accent_color(color)
        self.jarvis_button.set_accent_color(color)
        for toggle in getattr(self, "sidebar_toggles", []):
            toggle.set_accent_color(color)
        self.accent_value_label.setText(
            f"{self.accent_hex.upper()}  RGB {color.red()}, {color.green()}, {color.blue()}"
        )
        self.apply_styles()

    def choose_text_color(self):
        color = self.pick_color(self.text_color, "Выберите цвет текста")
        if not color.isValid():
            return

        self.text_color = color
        self.text_color_hex = color.name()
        self.ui_settings.setValue("font_color", self.text_color_hex)
        self.hud.set_text_color(color)
        self.jarvis_button.set_text_color(color)
        self.font_color_value_label.setText(
            f"{self.text_color_hex.upper()}  RGB {color.red()}, {color.green()}, {color.blue()}"
        )
        self.apply_styles()


    # ---------------- HOVER MENU BUTTON ----------------

    def eventFilter(self, obj, event):

        if self.panel_calibration_mode and obj in getattr(self, "hud_panel_button_map", {}).values():
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._panel_drag = (obj, event.position().toPoint(), obj.pos())
                return True
            if event.type() == QEvent.MouseMove and self._panel_drag:
                dragged, start, origin = self._panel_drag
                delta = event.position().toPoint() - start
                dragged.move(origin + delta)
                return True
            if event.type() == QEvent.MouseButtonRelease and self._panel_drag:
                dragged, _, _ = self._panel_drag
                self._panel_drag = None
                self.save_panel_position(dragged)
                return True

        if obj == self.chats_list.viewport():

            if event.type() == QEvent.MouseMove:

                pos = event.pos()

                for i in range(self.chats_list.count()):

                    item = self.chats_list.item(i)
                    widget = self.chats_list.itemWidget(item)

                    if not widget:
                        continue

                    rect = self.chats_list.visualItemRect(item)

                    if rect.contains(pos):
                        widget.menu_btn.show()
                    else:
                        widget.menu_btn.hide()

            elif event.type() == QEvent.Leave:

                for i in range(self.chats_list.count()):

                    item = self.chats_list.item(i)
                    widget = self.chats_list.itemWidget(item)

                    if widget:
                        widget.menu_btn.hide()

        return super().eventFilter(obj, event)

    def save_panel_position(self, button):
        for name, candidate in self.hud_panel_button_map.items():
            if candidate is button:
                self.widget_settings.setdefault("panel_positions", {})[name] = {
                    "x": button.x(),
                    "y": button.y(),
                    "angle": round(getattr(button, "panel_angle", 0), 1),
                }
                self.ui_settings.setValue(
                    "widget_settings",
                    json.dumps(self.widget_settings, ensure_ascii=False),
                )
                print(f"Panel position saved: {name} -> ({button.x()}, {button.y()})")
                return


    # ---------------- CHAT MENU ----------------

    def chat_menu(self, pos):

        item = self.chats_list.itemAt(pos)

        if not item:
            return

        menu = QMenu(self)

        menu.setStyleSheet(f"""
        QMenu{
        background:#1c1c24;
        border:1px solid rgba(255,255,255,40);
        border-radius:8px;
        color:white;
        padding:6px;
        }

        QMenu::item{
        padding:6px 8px;
        border-radius:6px;
        }

        QMenu::item:selected{
        background:{self.accent_hex};
        }
        """)

        pin_icon = QIcon(os.path.join(BASE_DIR,"assets","pin.svg"))
        edit_icon = QIcon(os.path.join(BASE_DIR,"assets","pencil.svg"))
        del_icon = QIcon(os.path.join(BASE_DIR,"assets","trash.svg"))

        pin_action = menu.addAction(pin_icon,"Закрепить")
        rename_action = menu.addAction(edit_icon,"Переименовать")
        delete_action = menu.addAction(del_icon,"Удалить")

        action = menu.exec(self.chats_list.mapToGlobal(pos))

        if action == pin_action:
            self.pin_chat(item)

        elif action == rename_action:
            self.rename_chat(item)

        elif action == delete_action:
            self.delete_chat(item)


    # ---------------- PIN CHAT ----------------

    def pin_chat(self, item):

        widget = self.chats_list.itemWidget(item)

        if not widget:
            return

        text = widget.label.text()
        row = self.chats_list.row(item)

        self.chats_list.takeItem(row)

        new_item = QListWidgetItem()
        new_widget = ChatItemWidget(text, pinned=True)

        new_item.setSizeHint(new_widget.sizeHint())

        self.chats_list.insertItem(0,new_item)
        self.chats_list.setItemWidget(new_item,new_widget)

        new_widget.menu_btn.clicked.connect(
            lambda: self.chat_menu(self.chats_list.visualItemRect(new_item).center())
        )


    # ---------------- RENAME CHAT ----------------

    def rename_chat(self, item):

        widget = self.chats_list.itemWidget(item)

        if not widget:
            return

        text, ok = QInputDialog.getText(
            self,
            "Переименовать чат",
            "Новое название:",
            text=widget.label.text()
        )

        if ok and text:
            widget.label.setText(text)


    # ---------------- DELETE CHAT ----------------

    def delete_chat(self, item):

        row = self.chats_list.row(item)
        self.chats_list.takeItem(row)


    # ---------------- ADD CHAT ITEM ----------------

    def add_chat_item(self, text, pinned=False):

        item = QListWidgetItem()

        widget = ChatItemWidget(text, pinned)

        item.setSizeHint(widget.sizeHint())

        self.chats_list.addItem(item)
        self.chats_list.setItemWidget(item, widget)

        widget.menu_btn.clicked.connect(
            lambda: self.chat_menu(self.chats_list.visualItemRect(item).center())
        )

    # ---------------- UI ----------------

    def build_ui(self):

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("container")
        self.main_container = container
        self.widget_chrome_widgets = []

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(30, 20, 30, 20)

        # ---------- HEADER ----------

        header = QHBoxLayout()

        title = QLabel("JARVIS ASSIST")
        title.setObjectName("title")
        self.widget_chrome_widgets.append(title)

        header.addWidget(title)
        header.addStretch()

        btn_min = QPushButton("–")
        btn_close = QPushButton("X")

        btn_min.setFixedSize(32, 32)
        btn_close.setFixedSize(32, 32)

        btn_close.setObjectName("closeBtn")
        self.widget_chrome_widgets.extend([btn_min, btn_close])

        btn_min.clicked.connect(self.showMinimized)
        btn_close.clicked.connect(self.close)

        header.addWidget(btn_min)
        header.addWidget(btn_close)

        container_layout.addLayout(header)

        # ---------- MAIN ----------

        main = QHBoxLayout()
        main.setSpacing(25)

        # ---------- LEFT PANEL ----------

        left = QVBoxLayout()
        left.setSpacing(15)

        self.menu = QListWidget()
        self.menu.setAttribute(Qt.WA_StyledBackground, True)
        self.menu.setObjectName("menu")

        self.menu.addItems([
            "АССИСТЕНТ",
            "НОВЫЙ ЧАТ",
            "ИСТОРИЯ ЧАТОВ",
            "НАСТРОЙКИ"
        ])

        self.menu.setFixedWidth(180)
        self.menu.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.menu.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.menu.setFixedHeight(200)
        self.widget_chrome_widgets.append(self.menu)

        left.addWidget(self.menu)


        # ---------- PINNED CHATS ----------

        # заголовок чатов
        chats_title = QLabel("Закрепленные чаты")
        chats_title.setStyleSheet("color:#888; font-size:12px;")
        self.widget_chrome_widgets.append(chats_title)

        left.addWidget(chats_title)

        # список чатов
        self.chats_list = QListWidget()
        self.chats_list.setObjectName("chatList")
        self.chats_list.setFixedWidth(180)

        self.chats_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chats_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chats_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chats_list.customContextMenuRequested.connect(self.chat_menu)
        self.chats_list.setFixedHeight(110)
        self.widget_chrome_widgets.append(self.chats_list)

        self.chats_list.addItems([
            "Приручаем Кешу",
            "Crazy Tad",
            "ТЗ для музыкальной платформы"
        ])

        left.addWidget(self.chats_list)


        # ---------- TOGGLES ----------

        toggles = QFrame()
        toggles.setObjectName("miniCard")
        toggles.setFixedSize(180,80)
        self.widget_chrome_widgets.append(toggles)

        t_layout = QVBoxLayout(toggles)

        row1 = QHBoxLayout()
        label1 = QLabel("Ассистент")
        label1.setStyleSheet("color:white; font-size:14px;")
        toggle1 = ToggleSwitch()
        toggle1.set_accent_color(self.accent_color)

        row1.addWidget(label1)
        row1.addStretch()
        row1.addWidget(toggle1)


        row2 = QHBoxLayout()
        label2 = QLabel("Микрофон")
        label2.setStyleSheet("color:white; font-size:14px;")
        toggle2 = ToggleSwitch()
        toggle2.set_accent_color(self.accent_color)
        self.sidebar_toggles = [toggle1, toggle2]

        row2.addWidget(label2)
        row2.addStretch()
        row2.addWidget(toggle2)

        t_layout.addLayout(row1)
        t_layout.addLayout(row2)


        # ---------- WEATHER ----------

        weather = QFrame()
        weather.setObjectName("miniCard")
        weather.setFixedSize(180,110)
        self.widget_chrome_widgets.append(weather)

        w_layout = QVBoxLayout(weather)
        w_layout.setAlignment(Qt.AlignCenter)

        self.weather_icon = QLabel()
        self.weather_icon.setAlignment(Qt.AlignCenter)

        self.weather_label = QLabel("Загрузка...")
        self.weather_label.setAlignment(Qt.AlignCenter)
        self.weather_label.setStyleSheet("color:white")

        w_layout.addWidget(self.weather_icon)
        w_layout.addWidget(self.weather_label)


        # ---------- LAYOUT ----------

        left.addStretch()

        left.addWidget(toggles)
        left.addWidget(weather)

    
        # ---------- CHAT ----------

        chat_frame = QFrame()
        chat_frame.setObjectName("chatFrame")

        chat_layout = QVBoxLayout(chat_frame)
        chat_layout.setContentsMargins(20, 20, 20, 20)
        chat_layout.setSpacing(20)

        # SCROLL AREA CHAT

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("background: transparent;")

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(10)

        self.scroll.setWidget(self.chat_container)

        chat_layout.addWidget(self.scroll)

        # ---------- INPUT ----------

        input_row = QHBoxLayout()
        input_row.setAlignment(Qt.AlignCenter)

        plus = QPushButton("+")
        plus.setFixedSize(40, 40)

        plus_menu = QMenu()
        plus_menu.addAction("Фото")
        plus_menu.addAction("Файл")
        plus_menu.addAction("Команда")
        plus_menu.addAction("Поиск в сети")

        plus.setMenu(plus_menu)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Спросите JARVIS или дайте команду")
        self.input.setFixedSize(610, 50)

        send = QPushButton("➤")
        send.setFixedSize(40, 40)

        send.clicked.connect(self.send_command)
        self.input.returnPressed.connect(self.send_command)

        input_row.addWidget(plus)
        input_row.addWidget(self.input)
        input_row.addWidget(send)

        chat_layout.addLayout(input_row)

        # ---------- PAGES ----------

        self.pages = QStackedWidget()

        # страница ассистента
        assistant_page = QWidget()

        assistant_layout = QVBoxLayout(assistant_page)
        assistant_layout.setContentsMargins(0,0,0,0)
        self.hud = JarvisHUD(
            self.accent_color,
            self.active_font_family,
            self.text_color,
            calibration_mode="--calibrate-cpu" in sys.argv,
        )
        self.hud.apply_widget_settings(self.widget_settings)
        self.hud.set_datetime_settings(self.widget_settings.get("datetime", {}))
        self.hud.setFixedSize(JarvisHUD.HUD_SIZE, JarvisHUD.HUD_SIZE)
        self.assistant_label = QLabel("Нажмите кнопку чтобы активировать JARVIS")
        self.assistant_label.setAlignment(Qt.AlignCenter)
        self.assistant_label.setStyleSheet("color:white; font-size:16px;")
        self.assistant_label.setFixedHeight(30)

        # состояние jarvis
        self.jarvis_state = False

        # кнопка jarvis
        self.jarvis_button = StartButton("START", self.text_color, self.accent_color)
        self.jarvis_button.setFixedSize(150,150)
        self.jarvis_button.setObjectName("jarvisStart")
        self.jarvis_button.setCursor(Qt.PointingHandCursor)

        # эффект свечения вокруг кнопки
        self.glow = QGraphicsDropShadowEffect()
        self.glow.setBlurRadius(60)
        self.glow.setColor(QColor(0,170,255))
        self.glow.setOffset(0)

        # анимация пульса
        self.pulse_anim = QPropertyAnimation(self.glow, b"blurRadius")
        self.pulse_anim.setStartValue(20)
        self.pulse_anim.setEndValue(200)
        self.pulse_anim.setDuration(800)
        self.pulse_anim.setLoopCount(-1)

        # анимация "дыхания" кнопки
        self.jarvis_button.setGraphicsEffect(self.glow)

        assistant_layout.addStretch()

        hud_container = QWidget()
        hud_container.setFixedSize(JarvisHUD.HUD_SIZE, JarvisHUD.HUD_SIZE)

        stack = QStackedLayout(hud_container)
        stack.setStackingMode(QStackedLayout.StackAll)

        # слой HUD
        stack.addWidget(self.hud)

        # слой кнопки
        button_layer = QWidget()
        button_layout = QVBoxLayout(button_layer)
        button_layout.setAlignment(Qt.AlignCenter)

        button_layout.addWidget(self.jarvis_button)

        stack.addWidget(button_layer)

        # TECH-A action buttons are direct children of the HUD container so
        # their transparent PNGs stay above the rings without covering START.
        self.tech_action_buttons = self.create_tech_action_buttons(hud_container)
        self.hud_panel_buttons = self.create_hud_panel_buttons(hud_container)

        assistant_layout.addWidget(hud_container, alignment=Qt.AlignCenter)

        assistant_layout.addSpacing(20)

        assistant_layout.addWidget(
        self.assistant_label,
        alignment=Qt.AlignHCenter
        )

        assistant_layout.addStretch()

        self.jarvis_button.clicked.connect(self.activate_assistant)

        self.pages.addWidget(assistant_page)
        
        # страница чата
        chat_page = QWidget()
        chat_page_layout = QVBoxLayout(chat_page)
        chat_page_layout.setContentsMargins(0,0,0,0)
        chat_page_layout.addWidget(chat_frame)

        self.pages.addWidget(chat_page)

        # Keep the left navigation indices aligned with the stacked pages.
        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        history_layout.addWidget(QLabel("ИСТОРИЯ ЧАТОВ"))
        history_layout.addStretch()
        self.pages.addWidget(history_page)

        # страница настроек
        settings_page = QWidget()
        settings_page.setObjectName("settingsPage")
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.setContentsMargins(24, 24, 24, 24)
        settings_layout.setSpacing(14)

        settings_title = QLabel("НАСТРОЙКИ JARVIS")
        settings_title.setObjectName("settingsTitle")
        settings_layout.addWidget(settings_title)
        settings_subtitle = QLabel("Внешний вид интерфейса и HUD")
        settings_subtitle.setObjectName("settingsHint")
        settings_layout.addWidget(settings_subtitle)

        typography_card = QFrame()
        typography_card.setObjectName("settingsCard")
        typography_layout = QVBoxLayout(typography_card)
        typography_title = QLabel("ТИПОГРАФИКА")
        typography_title.setObjectName("settingsCardTitle")
        typography_layout.addWidget(typography_title)
        typography_layout.addWidget(QLabel("Шрифт интерфейса TECH-A"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(list(self.tech_font_families.keys()))
        for index, family in enumerate(self.font_combo.itemText(i) for i in range(self.font_combo.count())):
            if self.tech_font_families.get(family) == self.active_font_family:
                self.font_combo.setCurrentIndex(index)
                break
        self.font_combo.currentTextChanged.connect(self.apply_font_family)
        typography_layout.addWidget(self.font_combo)
        font_hint = QLabel("Шрифт применяется к вкладкам и живому тексту HUD.")
        font_hint.setObjectName("settingsHint")
        typography_layout.addWidget(font_hint)
        settings_layout.addWidget(typography_card)

        colors_card = QFrame()
        colors_card.setObjectName("settingsCard")
        colors_layout = QVBoxLayout(colors_card)
        colors_title = QLabel("ЦВЕТА")
        colors_title.setObjectName("settingsCardTitle")
        colors_layout.addWidget(colors_title)
        colors_layout.addWidget(QLabel("Акцентный цвет интерфейса и индикаторов"))
        self.accent_value_label = QLabel()
        self.accent_value_label.setText(
            f"{self.accent_hex.upper()}  RGB {self.accent_color.red()}, "
            f"{self.accent_color.green()}, {self.accent_color.blue()}"
        )
        self.accent_button = QPushButton("Изменить акцентный цвет")
        self.accent_button.clicked.connect(self.choose_accent_color)
        colors_layout.addWidget(self.accent_value_label)
        colors_layout.addWidget(self.accent_button)
        colors_layout.addWidget(QLabel("Цвет текста интерфейса и показателей HUD"))
        self.font_color_value_label = QLabel()
        self.font_color_value_label.setText(
            f"{self.text_color_hex.upper()}  RGB {self.text_color.red()}, "
            f"{self.text_color.green()}, {self.text_color.blue()}"
        )
        self.font_color_button = QPushButton("Изменить цвет текста")
        self.font_color_button.clicked.connect(self.choose_text_color)
        colors_layout.addWidget(self.font_color_value_label)
        colors_layout.addWidget(self.font_color_button)
        settings_layout.addWidget(colors_card)

        runtime_card = QFrame()
        runtime_card.setObjectName("settingsCard")
        runtime_layout = QFormLayout(runtime_card)
        runtime_title = QLabel("ЗВУК И ВИЗУАЛ")
        runtime_title.setObjectName("settingsCardTitle")
        runtime_layout.addRow(runtime_title)

        self.startup_diagnostic_check = QCheckBox("Говорить диагностику при запуске")
        self.startup_diagnostic_check.setChecked(
            self.ui_settings.value("startup_diagnostic_enabled", True, type=bool)
        )
        self.startup_diagnostic_check.toggled.connect(self.set_startup_diagnostic_enabled)
        runtime_layout.addRow(self.startup_diagnostic_check)

        self.startup_widget_check = QCheckBox("Запускать сразу в прозрачном VID-режиме")
        self.startup_widget_check.setChecked(self.startup_widget_mode)
        self.startup_widget_check.toggled.connect(self.set_startup_widget_mode)
        runtime_layout.addRow(self.startup_widget_check)

        self.audio_source_combo = QComboBox()
        for label, device_id in self.enumerate_audio_sources():
            self.audio_source_combo.addItem(label, device_id)
        audio_index = self.audio_source_combo.findData(self.hardware_settings["audio_input_device"])
        self.audio_source_combo.setCurrentIndex(max(0, audio_index))
        self.audio_source_combo.currentIndexChanged.connect(self.apply_hardware_settings)
        runtime_layout.addRow(QLabel("Микрофон"), self.audio_source_combo)

        self.video_source_combo = QComboBox()
        for label, device_id in self.enumerate_video_sources():
            self.video_source_combo.addItem(label, device_id)
        video_index = self.video_source_combo.findData(self.hardware_settings["video_input_device"])
        self.video_source_combo.setCurrentIndex(max(0, video_index))
        self.video_source_combo.currentIndexChanged.connect(self.apply_hardware_settings)
        runtime_layout.addRow(QLabel("Камера / видео"), self.video_source_combo)
        QTimer.singleShot(0, self.apply_hardware_settings)

        self.transparent_background_check = QCheckBox("Прозрачный фон окна")
        self.transparent_background_check.setChecked(self.visual_settings["transparent_background"])
        self.transparent_background_check.toggled.connect(self.apply_visual_settings)
        runtime_layout.addRow(self.transparent_background_check)

        self.glass_enabled_check = QCheckBox("Glass-градиент интерфейса")
        self.glass_enabled_check.setChecked(self.visual_settings["glass_enabled"])
        self.glass_enabled_check.toggled.connect(self.apply_visual_settings)
        runtime_layout.addRow(self.glass_enabled_check)

        self.acrylic_status = QLabel("Acrylic Windows: не подключён")
        self.acrylic_status.setObjectName("settingsHint")
        runtime_layout.addRow(self.acrylic_status)

        self.window_opacity_spin = QSpinBox()
        self.window_opacity_spin.setRange(20, 100)
        self.window_opacity_spin.setSuffix(" %")
        self.window_opacity_spin.setValue(self.visual_settings["window_opacity"])
        self.window_opacity_spin.valueChanged.connect(self.apply_visual_settings)
        runtime_layout.addRow(QLabel("Прозрачность окна и popup"), self.window_opacity_spin)
        settings_layout.addWidget(runtime_card)
        settings_layout.addStretch()
        self.pages.addWidget(settings_page)

        # страница команд
        commands_page = QWidget()
        commands_layout = QVBoxLayout(commands_page)
        commands_layout.addWidget(QLabel("НАСТРОЙКИ"))
        self.pages.addWidget(commands_page)

        main.addLayout(left)
        main.addWidget(self.pages)

        container_layout.addLayout(main)

        root.addWidget(container)

        self.apply_styles()

    # ---------------- WEATHER ----------------

    def load_weather(self):

        try:
            API_KEY = os.getenv("OPENWEATHER_API_KEY")

            if not API_KEY:
                self.weather_label.setText("Погода\nне настроена")
                return

            geo = requests.get("http://ip-api.com/json").json()
            city = geo["city"]

            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=ru"

            data = requests.get(url).json()

            temp = round(data["main"]["temp"])
            desc = data["weather"][0]["description"]

            icon = data["weather"][0]["icon"]
            icon_url = f"http://openweathermap.org/img/wn/{icon}@2x.png"

            img = requests.get(icon_url).content

            pixmap = QPixmap()
            pixmap.loadFromData(img)

            self.weather_icon.setPixmap(
                pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

            self.weather_label.setText(f"{city}\n{temp}°C\n{desc}")

        except:

            self.weather_label.setText("Погода\nнедоступна")    

    # ---------------- STYLES ----------------

    def apply_styles(self):

        accent = self.accent_hex
        accent_hover = self.accent_color.lighter(120).name()

        self.setStyleSheet("""

#container{

border-radius:30px;

background:qlineargradient(
x1:0,y1:0,
x2:1,y2:1,
stop:0 rgba(20,20,25,220),
stop:0.35 rgba(15,15,20,220),
stop:0.65 rgba(10,10,15,230),
stop:1 rgba(30,30,35,220)
);

border:1px solid rgba(255,255,255,40);

}

#title{
font-size:20px;
font-weight:bold;
color:#2E89FF;
}

#menu{
background: transparent;
border: none;
outline: none;
}

#menu::item{
height:50px;
color:white;
padding-left:16px;
border-radius:10px;
}

#menu::item:selected{
background:#2E89FF;
color:#111111;
}

#menu::item:hover{
background:#2E89FF;
color:white;
}

#hudPanelTop{
background:transparent;
border:1px solid transparent;
border-radius:4px;
color:#FFFFFF;
font-size:8px;
padding:1px 4px;
}

#hudPanelTop:hover{
background:rgba(0,235,245,45);
border:1px solid rgba(0,235,245,160);
color:#FFFFFF;
}

#hudPanelIcon{
background:transparent;
border:1px solid transparent;
border-radius:6px;
}

#hudPanelIcon:hover{
background:rgba(0,235,245,45);
border:1px solid rgba(0,235,245,160);
}
                           
#chatList{
background: transparent;
border: none;
outline: none;
}

#chatList::item{
color:white;
padding:6px;
border-radius:6px;
font-size:13px;
}

#chatList::item:selected{
background: rgba(255,255,255,0.08);
}

#chatList::item:hover{
background: rgba(255,255,255,0.05);
}

ChatItemWidget{
border-radius:8px;
}

ChatItemWidget:hover{
background: rgba(255,255,255,0.05);
}

#techTool{
background:transparent;
border:none;
padding:0;
}

#techTool:hover{
background:transparent;
border:none;
}

QPushButton{
border:none;
}

QPushButton:hover{
color:white;
}                                                      

#miniCard{
border:1px solid rgba(255,255,255,40);
border-radius:10px;
background:rgba(255,255,255,0.08);
}

QCheckBox::indicator:checked{
background:#2E89FF;
}       

QLabel{
color:#FFFFFF;
}

QComboBox{
color:#111;
background:rgba(255,255,255,220);
}

QComboBox QAbstractItemView{
color:#111;
background:white;
}

#settingsTitle{
font-size:22px;
font-weight:bold;
color:#FFFFFF;
}

#settingsCard{
border:1px solid rgba(255,255,255,45);
border-radius:14px;
background:rgba(255,255,255,0.07);
}

#settingsCardTitle{
font-size:12px;
font-weight:bold;
letter-spacing:2px;
color:#FFFFFF;
}

#settingsHint{
color:rgba(255,255,255,165);
font-size:12px;
}
                                               
#chatFrame{

border-radius:30px;
border:1px solid rgba(255,255,255,40);

background:qlineargradient(
x1:0,y1:0,
x2:1,y2:1,
stop:0 rgba(30,30,35,220),
stop:0.3 rgba(20,20,25,220),
stop:0.7 rgba(15,15,20,230),
stop:1 rgba(35,35,40,220)
);

}

QLineEdit{
background:rgba(255,255,255,200);
border-radius:10px;
padding-left:10px;
}

QPushButton{
background:#2E89FF;
border:none;
border-radius:8px;
color:white;
}

QPushButton:hover{
background:#4aa0ff;
}

#closeBtn{
background:#ff4d4d;
}

#closeBtn:hover{
background:#ff2c2c;
}

#jarvisStart{
color:rgba(235,250,255,245);
font-size:26px;
font-weight:bold;
letter-spacing:3px;
border-radius:75px;
border:1px solid rgba(220,250,255,180);
background:qradialgradient(
cx:0.5, cy:0.42, radius:0.62,
 stop:0 rgba(220,250,255,235),
 stop:0.34 rgba(90,190,230,220),
 stop:0.72 rgba(25,70,100,235),
 stop:1 rgba(8,18,28,245)
);
}

#jarvisStart:hover{
border:2px solid rgba(235,255,255,230);
background:qradialgradient(
cx:0.5, cy:0.42, radius:0.62,
 stop:0 rgba(240,255,255,245),
 stop:0.34 rgba(80,210,255,230),
 stop:1 rgba(8,18,28,245)
);
}

#jarvisStart[active="true"]{
color:#bdf7ff;
border:2px solid rgba(0,220,255,235);
background:qradialgradient(
cx:0.5, cy:0.42, radius:0.62,
 stop:0 rgba(235,255,255,245),
 stop:0.32 rgba(0,210,255,235),
 stop:1 rgba(5,35,55,248)
);
}
                           
                         
QCheckBox::indicator{
width:40px;
height:22px;
border-radius:11px;
background:#444;
}

""".replace("#2E89FF", accent)
        .replace("#4aa0ff", accent_hover)
        .replace("#FFFFFF", self.text_color_hex))

        if hasattr(self, "main_container") and not getattr(self, "widget_mode", False):
            self.main_container.setStyleSheet(self.container_visual_stylesheet())


    # ---------------- COMMAND ----------------

    def send_command(self):

        text = self.input.text().strip()

        if not text:
            return

        self.add_message(text, True)

        try:
            r = requests.post(
                API_URL,
                json={"message": text},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            answer = data.get("response", "Нет ответа")

        except:
            answer = "Ошибка соединения"

        self.add_message(answer, False)

        self.input.clear()

    # ---------------- CHAT ----------------

    def add_message(self, text, user):

        bubble = MessageBubble(text, user)

        self.chat_layout.addWidget(bubble)

        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    # ---------------- DRAG WINDOW ----------------

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()

if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = JarvisUI()
    window.show()

    sys.exit(app.exec())
