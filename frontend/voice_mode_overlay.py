from __future__ import annotations

import math

from pathlib import Path

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QParallelAnimationGroup, Property, QPropertyAnimation, QPoint, QPointF, QRectF, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QRadialGradient, QTransform
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class _OrbCanvas(QWidget):
    """Transparent canvas that paints a lightweight accent-colored glow behind the PNG."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._glow_strength = 0.35
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _get_glow_strength(self) -> float:
        return self._glow_strength

    def _set_glow_strength(self, value: float) -> None:
        self._glow_strength = max(0.0, min(1.0, float(value)))
        self.update()

    glowStrength = Property(float, _get_glow_strength, _set_glow_strength)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = self.rect().center()
        radius = max(1, min(self.width(), self.height()) // 2)
        gradient = QRadialGradient(center, radius * 0.78)
        alpha = int(105 * self._glow_strength)
        gradient.setColorAt(0.0, QColor(0, 170, 255, max(4, alpha // 4)))
        gradient.setColorAt(0.62, QColor(0, 170, 255, alpha))
        gradient.setColorAt(1.0, QColor(0, 170, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)
        super().paintEvent(event)


class _OrbRings(QWidget):
    """Three lightweight accent rings rotating around the Voice Mode Orb."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)

    def _advance(self) -> None:
        # Outer and inner rings turn left; the middle ring turns right.
        self._angle = (self._angle + 0.9) % 360.0
        self.update()

    def set_active(self, active: bool) -> None:
        if active:
            if not self._timer.isActive():
                self._timer.start()
            self.show()
            self.raise_()
        else:
            self._timer.stop()
            self.hide()

    def paintEvent(self, event) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = self.rect().center()
        max_radius = min(self.width(), self.height()) * 0.47
        glow = QRadialGradient(center, max_radius * 0.72)
        glow.setColorAt(0.0, QColor(0, 175, 255, 58))
        glow.setColorAt(0.48, QColor(0, 170, 255, 28))
        glow.setColorAt(1.0, QColor(0, 170, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, max_radius * 0.72, max_radius * 0.72)
        # The wider ring canvas leaves a visible breathing gap between the
        # supplied Orb image and the HUD geometry.
        rings = (
            (max_radius * 0.56, self._angle, 220),
            (max_radius * 0.75, -self._angle * 0.72, 195),
            (max_radius * 0.93, self._angle * 0.48, 145),
        )
        inner_radius, inner_angle, inner_alpha = rings[0]
        inner_rect = QRectF(center.x() - inner_radius, center.y() - inner_radius, inner_radius * 2, inner_radius * 2)
        inner_pen = QPen(QColor(0, 170, 255, inner_alpha))
        inner_pen.setWidthF(0.9)
        painter.setPen(inner_pen)
        # Deliberately incomplete inner orbit.
        painter.drawArc(inner_rect, int((inner_angle * 16) % 5760), 285 * 16)

        middle_radius, middle_angle, middle_alpha = rings[1]
        middle_rect = QRectF(center.x() - middle_radius, center.y() - middle_radius, middle_radius * 2, middle_radius * 2)
        middle_pen = QPen(QColor(0, 170, 255, middle_alpha))
        middle_pen.setWidthF(0.8)
        painter.setPen(middle_pen)
        painter.drawEllipse(middle_rect)
        thick_pen = QPen(QColor(0, 190, 255, 245))
        thick_pen.setWidthF(2.4)
        painter.setPen(thick_pen)
        painter.drawArc(middle_rect, int((middle_angle * 16) % 5760), 82 * 16)
        painter.drawArc(middle_rect, int(((middle_angle + 180) * 16) % 5760), 34 * 16)

        outer_radius, outer_angle, outer_alpha = rings[2]
        outer_rect = QRectF(center.x() - outer_radius, center.y() - outer_radius, outer_radius * 2, outer_radius * 2)
        dotted_pen = QPen(QColor(0, 170, 255, outer_alpha))
        dotted_pen.setWidthF(0.75)
        dotted_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(dotted_pen)
        painter.drawEllipse(outer_rect)

        # Three accent points orbit the dotted outer ring.
        for offset in (0.0, 120.0, 240.0):
            point_angle = math.radians(outer_angle + offset)
            px = center.x() + math.cos(point_angle) * outer_radius
            py = center.y() - math.sin(point_angle) * outer_radius
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 170, 255, 55))
            painter.drawEllipse(QPointF(px, py), 7.5, 7.5)
            painter.setBrush(QColor(0, 190, 255, 235))
            painter.drawEllipse(QPointF(px, py), 2.8, 2.8)
        painter.end()


class _VoiceWaveform(QWidget):
    """Accent waveform that follows microphone/VAD activity in Voice Mode."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._level = 0.04
        self._active = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(55)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def set_activity(self, level: float, active: bool) -> None:
        normalized = max(0.04, min(1.0, float(level)))
        self._level = max(normalized, 0.35 if active else 0.0)
        self._active = bool(active)
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + (0.22 if self._active else 0.08)) % (math.pi * 2)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        count = 15
        spacing = self.width() / (count + 1)
        center_y = self.height() / 2
        activity = self._level if self._active else 0.12
        for index in range(count):
            wave = abs(math.sin(self._phase + index * 0.63))
            height = 5.0 + (self.height() * 0.68) * activity * (0.28 + 0.72 * wave)
            x = spacing * (index + 1)
            glow_pen = QPen(QColor(0, 170, 255, 45))
            glow_pen.setWidthF(4.5)
            painter.setPen(glow_pen)
            painter.drawLine(QPointF(x, center_y - height / 2), QPointF(x, center_y + height / 2))
            pen = QPen(QColor(0, 190, 255, 235))
            pen.setWidthF(1.7)
            painter.setPen(pen)
            painter.drawLine(QPointF(x, center_y - height / 2), QPointF(x, center_y + height / 2))
        painter.end()


class VoiceModeOverlay(QFrame):
    """A child overlay for the existing chat page, backed by real voice state."""

    stop_requested = Signal()

    _FRAMES = {
        "waiting": ["01 - ждет.png"],
        "processing": [f"02 - обработка ({index}).png" for index in range(1, 6)],
        "speaking": [f"03 - говорит ({index}).png" for index in range(1, 5)],
    }
    _SEQUENCES = {
        "waiting": [0],
        # 1 -> 2 -> 3 -> 4 -> 5 -> 4 -> 3 -> 2 -> repeat.
        "processing": [0, 1, 2, 3, 4, 3, 2, 1],
        # Keep the requested speaking frame static; scale/glow pulse carries
        # the voice activity without cycling through the other PNGs.
        "speaking": [1],
    }
    _LABELS = {
        "waiting": "Ожидаю команду",
        "processing": "Обрабатываю запрос",
        "speaking": "Jarvis говорит",
    }
    _ORB_DISPLAY_SCALE = 0.30
    _ANIMATION_ENABLED = True
    _MOTION_ENABLED = True

    def __init__(self, asset_root: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.asset_root = Path(asset_root)
        self.orb_root = self.asset_root / "orb"
        self._state = "waiting"
        self._frame_index = 0
        self._sequence_index = 0
        self._current_layer = 0
        self._hovered = False
        self._hover_restart_connected = False
        self._visual_scale = 1.0
        self._rotation_angle = 0.0
        self._last_hover_pos = None
        self._crossfade: QParallelAnimationGroup | None = None
        self._layer_sources = [QPixmap(), QPixmap()]
        self._orb_base_rect = None
        self._orb_host: QWidget | None = None
        self._orb_bounds: QWidget | None = None
        self._fullscreen_centered = False
        self._orb_rings: _OrbRings | None = None
        self._calibration_mode = False
        self._drag_anchor = None
        self._resize_anchor = None
        self._calibration_settings = QSettings("Jarvis", "Jarvis Assist")
        self._build_ui()
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._advance_frame)
        self._breath = QPropertyAnimation(self, b"visualScale", self)
        self._breath.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._breath.setDuration(2600)
        self._breath.setLoopCount(-1)
        self._glow = QPropertyAnimation(self.orb_canvas, b"glowStrength", self)
        self._glow.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._glow.setDuration(2200)
        self._glow.setLoopCount(-1)
        self._hover_animation = QPropertyAnimation(self, b"visualScale", self)
        self._hover_animation.setDuration(280)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._rotation_animation = QPropertyAnimation(self, b"rotationAngle", self)
        self._rotation_animation.setDuration(420)
        self._rotation_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.set_state("waiting")
        self.hide()

    def _build_ui(self) -> None:
        self.setObjectName("voiceModeOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(
            "QLabel#voiceModeTitle { color: #ffffff; font-size: 22px; font-weight: 700; }"
            "QLabel#voiceModeState { color: #00aaff; font-size: 15px; }"
            "QLabel#voiceModeDetail { color: rgba(255,255,255,190); font-size: 12px; }"
            "QPushButton#voiceModeStop { background: rgba(0,170,255,0.2); border: 1px solid #00aaff; "
            "border-radius: 15px; color: white; padding: 9px 24px; font-size: 13px; }"
            "QPushButton#voiceModeStop:hover { background: rgba(0,200,255,0.38); }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(8)
        title = QLabel("JARVIS VOICE MODE")
        title.setObjectName("voiceModeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        self.state_label = QLabel()
        self.state_label.setObjectName("voiceModeState")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.state_label)
        self.orb_canvas = _OrbCanvas(self)
        self.orb_canvas.setObjectName("voiceModeOrbCanvas")
        self.orb_canvas.setMinimumSize(280, 280)
        self.orb_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.orb_canvas.setMouseTracking(True)
        self.orb_stage = QWidget(self.orb_canvas)
        self.orb_stage.setObjectName("voiceModeOrbStage")
        self.orb_stage.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.orb_stage.setMouseTracking(True)
        self.orb_stage.installEventFilter(self)
        self.orb_canvas.installEventFilter(self)
        self.glow_effect = QGraphicsDropShadowEffect(self.orb_stage)
        self.glow_effect.setOffset(0, 0)
        self.glow_effect.setColor("#00aaff")
        self.glow_effect.setBlurRadius(38)
        # Do not attach a QGraphicsEffect to the parent of the image layers:
        # on some Qt/Windows paint paths it renders the transparent parent
        # without its child QLabel contents. The supplied PNGs already contain
        # their own glow; keep the effect as state metadata without hiding the orb.
        self.layers = []
        for index in range(2):
            label = QLabel(self.orb_stage)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            opacity = QGraphicsOpacityEffect(label)
            label.setGraphicsEffect(opacity)
            self.layers.append((label, opacity))
        # The orb is positioned as an absolute child of the overlay. Keeping
        # it inside the layout caused a clipping race when the parent was a
        # QWebEngineView and the overlay was opened more than once.
        root.addStretch(1)
        self.voice_waveform = _VoiceWaveform(self)
        self.voice_waveform.setObjectName("voiceModeWaveform")
        self.voice_waveform.setFixedSize(170, 56)
        root.addWidget(self.voice_waveform, 0, Qt.AlignmentFlag.AlignCenter)
        self.detail_label = QLabel("Голосовой диалог использует текущий чат")
        self.detail_label.setObjectName("voiceModeDetail")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setWordWrap(True)
        root.addWidget(self.detail_label)
        controls = QHBoxLayout()
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stop_button = QPushButton("Завершить диалог")
        self.stop_button.setObjectName("voiceModeStop")
        self.stop_button.clicked.connect(self.stop_requested)
        controls.addWidget(self.stop_button)
        self.calibration_button = QPushButton("Зафиксировать Orb")
        self.calibration_button.setObjectName("voiceModeCalibration")
        self.calibration_button.clicked.connect(self.save_calibration)
        self.calibration_button.setVisible(False)
        controls.addWidget(self.calibration_button)
        root.addLayout(controls)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(5, 9, 16, 238))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 24, 24)
        super().paintEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_orb()

    def set_orb_host(self, host: QWidget, bounds: QWidget | None = None) -> None:
        """Render the orb above the overlay, positioned from the chat bounds."""
        self._orb_host = host
        self._orb_bounds = bounds or host
        self._orb_rings = _OrbRings(host)
        self._orb_rings.hide()
        self.orb_canvas.setParent(host)
        # Reparenting a QWidget can implicitly expose it on Windows/Qt.
        # The orb must remain hidden until Voice Mode explicitly opens.
        self.orb_canvas.hide()
        host.installEventFilter(self)
        if self._orb_bounds is not host:
            self._orb_bounds.installEventFilter(self)
        self._layout_orb()

    def set_calibration_mode(self, enabled: bool) -> None:
        self._calibration_mode = bool(enabled)
        self.calibration_button.setVisible(self._calibration_mode)
        self.orb_canvas.setCursor(Qt.CursorShape.SizeAllCursor if enabled else Qt.CursorShape.ArrowCursor)

    def set_fullscreen_centered(self, enabled: bool) -> None:
        """Use a deterministic centered layout while the shell is fullscreen."""
        self._fullscreen_centered = bool(enabled)
        self._layout_orb()

    def _get_visual_scale(self) -> float:
        return self._visual_scale

    def _set_visual_scale(self, value: float) -> None:
        self._visual_scale = max(0.94, min(1.08, float(value)))
        self._set_stage_pixmaps()

    visualScale = Property(float, _get_visual_scale, _set_visual_scale)

    def _get_rotation_angle(self) -> float:
        return self._rotation_angle

    def _set_rotation_angle(self, value: float) -> None:
        self._rotation_angle = float(value)
        self._set_stage_pixmaps()

    rotationAngle = Property(float, _get_rotation_angle, _set_rotation_angle)

    def _saved_calibration_rect(self):
        size = int(self._calibration_settings.value("voice_orb_size", 0) or 0)
        if size <= 0:
            return None
        return (
            int(self._calibration_settings.value("voice_orb_x", 0) or 0),
            int(self._calibration_settings.value("voice_orb_y", 0) or 0),
            size,
        )

    def save_calibration(self) -> None:
        host = self._orb_host
        bounds = self._orb_bounds or host
        if host is None or bounds is None:
            return
        bounds_pos = bounds.mapTo(host, QPoint(0, 0)) if bounds is not host else QPoint(0, 0)
        rect = self.orb_canvas.geometry()
        self._calibration_settings.setValue("voice_orb_x", rect.x() - bounds_pos.x())
        self._calibration_settings.setValue("voice_orb_y", rect.y() - bounds_pos.y())
        self._calibration_settings.setValue("voice_orb_size", rect.width())
        self._calibration_settings.sync()
        self._calibration_settings.setValue("voice_orb_calibrated", True)
        self._calibration_settings.sync()
        self.detail_label.setText(f"Orb зафиксирован: {rect.width()} px")

    def _layout_orb(self) -> None:
        host = self._orb_host or self
        bounds = self._orb_bounds or host
        if bounds.width() <= 0 or bounds.height() <= 0:
            return
        bounds_pos = bounds.mapTo(host, QPoint(0, 0)) if bounds is not host else QPoint(0, 0)
        max_side = max(220, min(bounds.width(), bounds.height()))
        saved = (
            self._saved_calibration_rect()
            if self._calibration_mode and not self._fullscreen_centered
            else None
        )
        native_side = self._native_orb_side()
        if self._fullscreen_centered:
            side = min(native_side, max_side)
        else:
            # Windowed Voice Mode shares the chat frame with title, waveform,
            # transcript and controls. Keep the visual stage inside the
            # central band instead of reusing the expansive fullscreen scale.
            windowed_cap = max(240, min(320, round(bounds.height() * 0.36)))
            side = min(saved[2] if saved else native_side, max_side, windowed_cap)
        if saved:
            x = bounds_pos.x() + max(0, min(saved[0], bounds.width() - side))
            saved_y = max(0, min(saved[1], bounds.height() - side))
            y = bounds_pos.y() + saved_y
        else:
            x = bounds_pos.x() + (bounds.width() - side) // 2
            if self._fullscreen_centered:
                y = bounds_pos.y() + (bounds.height() - side) // 2
            else:
                top_reserve = min(100, max(64, bounds.height() // 8))
                bottom_reserve = min(180, max(130, bounds.height() // 5))
                usable_height = max(side, bounds.height() - top_reserve - bottom_reserve)
                y = bounds_pos.y() + top_reserve + (usable_height - side) // 2
        self.orb_canvas.setGeometry(x, y, side, side)
        self.orb_stage.setGeometry(0, 0, side, side)
        if self._orb_rings is not None:
            ring_side = (
                max(side + 200, round(side * 2.55))
                if self._fullscreen_centered
                else max(side + 150, round(side * 1.72))
            )
            self._orb_rings.setGeometry(
                x - (ring_side - side) // 2,
                y - (ring_side - side) // 2,
                ring_side,
                ring_side,
            )
        self._orb_base_rect = self.orb_canvas.geometry()
        self._set_stage_pixmaps()
        self._set_layer_pixmaps()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.orb_stage:
            if event.type() == event.Type.Enter:
                self._hovered = True
                self._last_hover_pos = event.position()
                self._set_glow_range()
                if not self._calibration_mode:
                    self._animate_hover(True)
            elif event.type() == event.Type.Leave:
                self._hovered = False
                self._last_hover_pos = None
                self._set_glow_range()
                if not self._calibration_mode:
                    self._animate_hover(False)
                    self._animate_rotation_back()
            elif event.type() == event.Type.MouseButtonPress:
                return self._calibration_mouse_press(event)
            elif event.type() == event.Type.MouseMove:
                if not self._calibration_mode:
                    self._update_hover_rotation(event)
                return self._calibration_mouse_move(event)
            elif event.type() == event.Type.MouseButtonRelease:
                return self._calibration_mouse_release(event)
        elif watched in (self._orb_host, self._orb_bounds) and event.type() == event.Type.Resize:
            if watched is self._orb_bounds and self.parentWidget() is watched:
                # Voice Mode is an absolute child so it cannot rely on a
                # layout-managed resize when the shell changes mode.
                self.setGeometry(watched.rect())
            self._layout_orb()
        return super().eventFilter(watched, event)

    def _calibration_mouse_press(self, event) -> bool:
        if not self._calibration_mode or event.button() != Qt.MouseButton.LeftButton:
            return False
        pos = event.position().toPoint()
        rect = self.orb_canvas.rect()
        if pos.x() >= rect.width() - 24 and pos.y() >= rect.height() - 24:
            self._resize_anchor = (event.globalPosition().toPoint(), self.orb_canvas.geometry())
        else:
            self._drag_anchor = (event.globalPosition().toPoint(), self.orb_canvas.geometry())
        return True

    def _calibration_mouse_move(self, event) -> bool:
        if not self._calibration_mode:
            return False
        host = self._orb_host
        bounds = self._orb_bounds or host
        if host is None or bounds is None:
            return False
        bounds_pos = bounds.mapTo(host, QPoint(0, 0)) if bounds is not host else QPoint(0, 0)
        if self._resize_anchor:
            start, original = self._resize_anchor
            delta = event.globalPosition().toPoint() - start
            max_side = min(bounds.width(), bounds.height())
            side = max(220, min(max_side, original.width() + max(delta.x(), delta.y())))
            x = max(bounds_pos.x(), min(original.x(), bounds_pos.x() + bounds.width() - side))
            y = max(bounds_pos.y(), min(original.y(), bounds_pos.y() + bounds.height() - side))
            self.orb_canvas.setGeometry(x, y, side, side)
        elif self._drag_anchor:
            start, original = self._drag_anchor
            delta = event.globalPosition().toPoint() - start
            x = max(bounds_pos.x(), min(original.x() + delta.x(), bounds_pos.x() + bounds.width() - original.width()))
            y = max(bounds_pos.y(), min(original.y() + delta.y(), bounds_pos.y() + bounds.height() - original.height()))
            self.orb_canvas.move(x, y)
        else:
            return False
        self.orb_stage.setGeometry(0, 0, self.orb_canvas.width(), self.orb_canvas.height())
        self._set_stage_pixmaps()
        self._set_layer_pixmaps()
        return True

    def _calibration_mouse_release(self, event) -> bool:
        if not self._calibration_mode or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._drag_anchor = None
        self._resize_anchor = None
        return True

    def show_mode(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.show()
        self.raise_()
        self._layout_orb()
        if self._orb_rings is not None:
            self._orb_rings.set_active(True)
        self.orb_canvas.show()
        self.orb_canvas.raise_()
        self._refresh_current_frame()
        self.set_state(self._state)

    def _refresh_current_frame(self) -> None:
        self._set_stage_pixmaps()
        self._set_layer_pixmaps()
        self._load_frame(self._frame_index, immediate=True)

    def hide_mode(self) -> None:
        self._frame_timer.stop()
        self._breath.stop()
        self._glow.stop()
        self._hover_animation.stop()
        self._rotation_animation.stop()
        if self._orb_rings is not None:
            self._orb_rings.set_active(False)
        self._set_visual_scale(1.0)
        self._set_rotation_angle(0.0)
        self.orb_canvas.hide()
        self.hide()

    def set_state(self, state: str) -> None:
        state = state if state in self._FRAMES else "waiting"
        if state == self._state:
            if self.isVisible():
                sequence = self._SEQUENCES[state]
                if self._ANIMATION_ENABLED and len(sequence) > 1 and not self._frame_timer.isActive():
                    self._frame_timer.start({"waiting": 3000, "processing": 480, "speaking": 420}[state])
                if (
                    self._ANIMATION_ENABLED
                    and self._MOTION_ENABLED
                    and not self._hovered
                    and self._breath.state() != QAbstractAnimation.State.Running
                    and self._hover_animation.state() != QAbstractAnimation.State.Running
                ):
                    self._start_motion()
            return
        previous_state = self._state
        self._state = state
        self._frame_index = 0
        self._sequence_index = 0
        self.state_label.setText(self._LABELS[state])
        interval = {"waiting": 3000, "processing": 480, "speaking": 420}[state]
        self._frame_timer.stop()
        transition = state != previous_state and self.isVisible() and self._ANIMATION_ENABLED
        first_frame = self._SEQUENCES[state][0]
        self._load_frame(first_frame, immediate=not transition)
        if self._ANIMATION_ENABLED and len(self._SEQUENCES[state]) > 1:
            self._frame_timer.start(interval)
        self._breath.stop()
        self._glow.stop()
        if self._ANIMATION_ENABLED and self._MOTION_ENABLED:
            self._start_motion()

    def set_dialogue(self, transcript: str = "", response: str = "") -> None:
        if transcript:
            self.detail_label.setText(f"Вы: {transcript}")
        elif response:
            self.detail_label.setText(response[:240])

    def set_voice_activity(self, level: float, active: bool) -> None:
        self.voice_waveform.set_activity(level, active)

    def _start_motion(self) -> None:
        if self._hovered:
            return
        # Keep the response pulse readable instead of letting it flicker.
        durations = {"waiting": 3200, "processing": 1900, "speaking": 2880}
        peaks = {"waiting": (0.98, 1.02, 0.28, 0.62), "processing": (0.985, 1.03, 0.32, 0.70), "speaking": (0.98, 1.055, 0.42, 0.95)}
        start_scale, peak_scale, start_glow, peak_glow = peaks[self._state]
        self._breath.setDuration(durations[self._state])
        self._breath.setStartValue(start_scale)
        self._breath.setKeyValueAt(0.5, peak_scale)
        self._breath.setEndValue(start_scale)
        self._breath.start()
        self._glow.setDuration(durations[self._state])
        self._glow.setStartValue(start_glow)
        self._glow.setKeyValueAt(0.5, peak_glow)
        self._glow.setEndValue(start_glow)
        self._glow.start()
        self._set_glow_range()

    def _animate_hover(self, entered: bool) -> None:
        self._hover_animation.stop()
        if entered:
            self._breath.stop()
            self._glow.stop()
        self._hover_animation.setStartValue(self._visual_scale)
        self._hover_animation.setEndValue(1.06 if entered else 1.0)
        if not entered and self._state in self._FRAMES:
            if self._hover_restart_connected:
                self._hover_animation.finished.disconnect(self._restart_motion_once)
            self._hover_animation.finished.connect(self._restart_motion_once)
            self._hover_restart_connected = True
        self._hover_animation.start()

    def _restart_motion_once(self) -> None:
        if self._hover_restart_connected:
            self._hover_animation.finished.disconnect(self._restart_motion_once)
            self._hover_restart_connected = False
        if not self._hovered and self.isVisible() and self._MOTION_ENABLED:
            self._start_motion()

    def _animate_rotation_back(self) -> None:
        self._rotation_animation.stop()
        self._rotation_animation.setStartValue(self._rotation_angle)
        self._rotation_animation.setEndValue(0.0)
        self._rotation_animation.start()

    def _update_hover_rotation(self, event) -> None:
        if self._state != "waiting" or not self._hovered:
            return
        current = event.position()
        previous = self._last_hover_pos
        self._last_hover_pos = current
        if previous is None:
            return
        center = self.orb_stage.rect().center()
        previous_angle = math.atan2(previous.y() - center.y(), previous.x() - center.x())
        current_angle = math.atan2(current.y() - center.y(), current.x() - center.x())
        delta = math.degrees(current_angle - previous_angle)
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360
        self._rotation_animation.stop()
        # Another 50% reduction from the previous pointer-driven speed.
        self._set_rotation_angle(self._rotation_angle + (delta * 0.125))

    def _set_glow_range(self) -> None:
        if self._hovered:
            self.glow_effect.setBlurRadius(115 if self._state != "waiting" else 78)

    def _set_layer_pixmaps(self) -> None:
        side = max(160, self.orb_stage.width())
        for label, _ in self.layers:
            label.setGeometry(0, 0, side, side)

    def _set_stage_pixmaps(self) -> None:
        side = max(160, self.orb_stage.width())
        for (label, _), source in zip(self.layers, self._layer_sources):
            if not source.isNull():
                # Preserve the calibrated native size at rest. During a
                # rotation gesture leave a small margin for the transformed
                # bounding box so the sphere does not clip at the corners.
                rotation_margin = 0.84 if abs(self._rotation_angle) > 0.1 else 1.0
                scaled_side = max(1, round(side * self._visual_scale * rotation_margin))
                pixmap = source.scaled(QSize(scaled_side, scaled_side), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                if abs(self._rotation_angle) > 0.1:
                    pixmap = pixmap.transformed(QTransform().rotate(self._rotation_angle), Qt.TransformationMode.SmoothTransformation)
                label.setPixmap(pixmap)

    def _native_orb_side(self) -> int:
        for source in self._layer_sources:
            if not source.isNull():
                return max(220, round(source.width() * self._ORB_DISPLAY_SCALE))
        return 376

    def _load_frame(self, index: int, immediate: bool = False) -> None:
        files = self._FRAMES[self._state]
        path = self.orb_root / files[index % len(files)]
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.detail_label.setText(f"Не найден ресурс Orb: {path.name}")
            return
        target = 0 if immediate or not self._ANIMATION_ENABLED else 1 - self._current_layer
        label, opacity = self.layers[target]
        self._layer_sources[target] = pixmap
        self._set_stage_pixmaps()
        if immediate or not self._ANIMATION_ENABLED:
            opacity.setOpacity(1.0)
            other_opacity = self.layers[1 - target][1]
            other_opacity.setOpacity(0.0)
            self._current_layer = target
            return
        opacity.setOpacity(0.0)
        self._crossfade = QParallelAnimationGroup(self)
        fade_in = QPropertyAnimation(opacity, b"opacity", self._crossfade)
        fade_in.setDuration(120)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_out = QPropertyAnimation(self.layers[self._current_layer][1], b"opacity", self._crossfade)
        fade_out.setDuration(120)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        self._crossfade.addAnimation(fade_in)
        self._crossfade.addAnimation(fade_out)
        self._crossfade.finished.connect(lambda: setattr(self, "_current_layer", target))
        self._crossfade.start()

    def _advance_frame(self) -> None:
        sequence = self._SEQUENCES[self._state]
        if len(sequence) <= 1:
            return
        self._sequence_index = (self._sequence_index + 1) % len(sequence)
        self._frame_index = sequence[self._sequence_index]
        self._load_frame(self._frame_index)
