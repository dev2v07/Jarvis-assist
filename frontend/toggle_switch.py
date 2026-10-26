from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import Qt, QPropertyAnimation, Property
from PySide6.QtGui import QPainter, QColor


class ToggleSwitch(QCheckBox):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(42, 24)
        self.setCursor(Qt.PointingHandCursor)

        self._circle_pos = 3
        self.accent_color = QColor("#00ebf5")

        self.anim = QPropertyAnimation(self, b"circle_pos")
        self.anim.setDuration(180)

        self.stateChanged.connect(self.start_animation)

    def start_animation(self):

        if self.isChecked():
            self.anim.setStartValue(3)
            self.anim.setEndValue(21)
        else:
            self.anim.setStartValue(21)
            self.anim.setEndValue(3)

        self.anim.start()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.isChecked():
            bg = QColor(self.accent_color)
        else:
            bg = QColor("#444")

        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 42, 24, 12, 12)

        painter.setBrush(QColor("white"))
        painter.drawEllipse(self._circle_pos, 3, 18, 18)

    def set_accent_color(self, color):
        parsed = QColor(color)
        if parsed.isValid():
            self.accent_color = parsed
            self.update()

    def get_circle_pos(self):
        return self._circle_pos

    def set_circle_pos(self, pos):
        self._circle_pos = pos
        self.update()

    circle_pos = Property(int, get_circle_pos, set_circle_pos)
