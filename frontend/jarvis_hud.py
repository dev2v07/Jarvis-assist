import os
import math
import psutil
import GPUtil

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import (
    QPainter, QPixmap, QFont, QFontDatabase,
    QPen, QColor
)
from PySide6.QtCore import QTimer, Qt, QRectF
from tech_a_animation import TechAAnimation


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE_DIR, "assets", "TECH-A")
ROTATOR = os.path.join(ASSETS, "rotator")
FONTS = os.path.join(BASE_DIR, "assets", "fonts")

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


class JarvisHUD(QWidget):

    # TECH-A is authored as a 710x710 Rainmeter skin.
    HUD_SIZE = 710
    ROTATOR_SIZE = 351
    GAUGE_RADIUS = 300
    GAUGE_BG_SIZE = 82

    def __init__(self):
        super().__init__()

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # HUD PNG
        self.group = QPixmap(os.path.join(ASSETS, "Group.png"))
        self.bg1 = QPixmap(os.path.join(ASSETS, "BG1.png"))
        self.bg2 = QPixmap(os.path.join(ASSETS, "BG2.png"))
        self.bg3 = QPixmap(os.path.join(ASSETS, "BG3.png"))
        self.bg4 = QPixmap(os.path.join(ASSETS, "BG4.png"))
        self.bg5 = QPixmap(os.path.join(ASSETS, "BG5.png"))
        self.bg6 = QPixmap(os.path.join(ASSETS, "BG6.png"))

        # Rainmeter keeps these in a separate rotator config.
        self.rotator_1 = QPixmap(os.path.join(ROTATOR, "1xx.png"))
        self.rotator_2 = QPixmap(os.path.join(ROTATOR, "2x.png"))
        self.rotator_3 = QPixmap(os.path.join(ROTATOR, "3x.png"))

        self.scale = self.HUD_SIZE / self.bg6.width()
        self.setFixedSize(self.HUD_SIZE, self.HUD_SIZE)

        # Optional motion is isolated from static BG1-BG6 composition.
        self.animation = TechAAnimation()
        self.group_scale = 0.65

        # реальные данные
        self.cpu = self.ram = self.gpu = self.disk = 0

        # плавная анимация
        self.cpu_anim = self.ram_anim = self.gpu_anim = self.disk_anim = 0

        # шрифт
        font_path = os.path.join(FONTS, "GOODTIME.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        family = QFontDatabase.applicationFontFamilies(font_id)[0]

        self.font_big = QFont(family, 10)
        self.font_label = QFont(family, 7)

        # таймеры
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(1000)

    def update_stats(self):

        self.cpu = int(psutil.cpu_percent())
        self.ram = int(psutil.virtual_memory().percent)

        try:
            gpus = GPUtil.getGPUs()
            self.gpu = int(gpus[0].load * 100) if gpus else 0
        except:
            self.gpu = 0

        self.disk = int(psutil.disk_usage('C:/').percent)

    def animate(self):

        # BG1-BG6 remain static; this advances only the optional animation.
        self.animation.step()

        # Показатели движутся по той же орбитальной оси, что и кольца TECH-A.
        # Значение a2 уже является частью существующей рабочей анимации.
        self.cpu_anim += (self.cpu - self.cpu_anim) * 0.08
        self.ram_anim += (self.ram - self.ram_anim) * 0.08
        self.gpu_anim += (self.gpu - self.gpu_anim) * 0.08
        self.disk_anim += (self.disk - self.disk_anim) * 0.08

        self.update()

    def ring_pos(self, cx, cy, angle):

        r = self.GAUGE_RADIUS

        x = cx + r * math.cos(math.radians(angle))
        y = cy + r * math.sin(math.radians(angle))

        return x, y

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2

        # ---------- ЗАДНИЙ КРУГ (Group.png) ----------

        painter.setOpacity(0.35)
        self.draw(
        painter,
        self.group,
        self.animation.group_angle,
        cx,
        cy,
        self.scale * self.group_scale
        )
        painter.setOpacity(1)

        # ---------- HUD слои ----------

        # Original TECH-A order: six static 710x710 image meters.
        for pixmap in (self.bg1, self.bg2, self.bg3, self.bg4, self.bg5, self.bg6):
            self.draw(painter, pixmap, 0, cx, cy)

        # Separate rotator config: 1xx.png, 2x.png and 3x.png.
        self.draw_rotator(painter, self.rotator_1, self.animation.rotator_1, cx, cy)
        self.draw_rotator(painter, self.rotator_2, self.animation.rotator_2, cx, cy)
        self.draw_rotator_at(
            painter,
            self.rotator_3,
            self.animation.rotator_3,
            cx - self.ROTATOR_SIZE / 2 + 201,
            cy - self.ROTATOR_SIZE / 2 + 151,
        )

        # индикаторы (НЕ вращаются)
        orbit = self.animation.orbit_angle
        cpu_x, cpu_y = self.ring_pos(cx, cy, -90 + orbit)
        ram_x, ram_y = self.ring_pos(cx, cy, 0 + orbit)
        gpu_x, gpu_y = self.ring_pos(cx, cy, 90 + orbit)
        disk_x, disk_y = self.ring_pos(cx, cy, 180 + orbit)

        self.draw_gauge(painter, cpu_x, cpu_y, self.cpu_anim, "CPU")
        self.draw_gauge(painter, ram_x, ram_y, self.ram_anim, "RAM")
        self.draw_gauge(painter, gpu_x, gpu_y, self.gpu_anim, "GPU")
        self.draw_gauge(painter, disk_x, disk_y, self.disk_anim, "DISK")

    def draw(self, painter, pixmap, angle, cx, cy, scale_override=None):

     if pixmap.isNull():
        return

     painter.save()

     painter.translate(cx, cy)
     painter.rotate(angle)

     scale = scale_override if scale_override else self.scale

     w = pixmap.width() * scale
     h = pixmap.height() * scale

     scaled = pixmap.scaled(
        int(w),
        int(h),
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation
     )

     painter.drawPixmap(
        -scaled.width() / 2,
        -scaled.height() / 2,
        scaled
     )

     painter.restore()

    def draw_rotator(self, painter, pixmap, angle, cx, cy):
        if pixmap.isNull():
            return
        self.draw_rotator_at(painter, pixmap, angle, cx - pixmap.width() / 2, cy - pixmap.height() / 2)

    def draw_rotator_at(self, painter, pixmap, angle, x, y):
        if pixmap.isNull():
            return
        painter.save()
        painter.translate(x + pixmap.width() / 2, y + pixmap.height() / 2)
        painter.rotate(angle)
        painter.drawPixmap(-pixmap.width() / 2, -pixmap.height() / 2, pixmap)
        painter.restore()

    def draw_gauge(self, painter, x, y, value, label):

        painter.save()

        # BG1 под индикатор
        bg = self.bg1.scaled(
            self.GAUGE_BG_SIZE,
            self.GAUGE_BG_SIZE,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        painter.drawPixmap(
            int(x - bg.width() / 2),
            int(y - bg.height() / 2),
            bg
        )

        rect = QRectF(x - 16, y - 16, 30, 30)

        # подпись
        painter.setPen(Qt.white)
        painter.setFont(self.font_label)
        painter.drawText(x - 14, y - 20, label)

        # фон дуги
        pen_bg = QPen(QColor(120, 120, 120), 2)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 135 * 16, 270 * 16)

        # дуга нагрузки
        pen_val = QPen(QColor(0, 200, 255), 3)
        painter.setPen(pen_val)

        span = int(-value * 270 / 100 * 16)
        painter.drawArc(rect, 135 * 16, span)

        # процент
        painter.setPen(Qt.white)
        painter.setFont(self.font_big)
        painter.drawText(rect, Qt.AlignCenter, f"{int(value)}")

        painter.restore()
