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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE_DIR, "assets", "TECH-A")
ROTATOR = os.path.join(ASSETS, "rotator")
FONTS = os.path.join(BASE_DIR, "assets", "fonts")


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

        self.rot1 = QPixmap(os.path.join(ROTATOR, "1x.png"))
        self.rot2 = QPixmap(os.path.join(ROTATOR, "2x.png"))
        self.rot3 = QPixmap(os.path.join(ROTATOR, "1xx.png"))

        self.scale = self.HUD_SIZE / self.bg6.width()
        self.setFixedSize(self.HUD_SIZE, self.HUD_SIZE)

        # вращение колец
        self.a2 = self.a3 = self.a4 = self.a5 = self.a6 = 0
        self.r1 = self.r2 = self.r3 = 0

        # вращение заднего круга
        self.group_angle = 0
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

        # вращение HUD
        self.a6 -= 0.05
        self.a5 += 0.03
        self.a4 -= 0.04
        self.a3 += 0.06
        self.a2 -= 0.08

        self.r3 += 0.20
        self.r2 -= 0.12
        self.r1 += 0.16

        # вращение заднего круга
        self.group_angle += 0.01

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
        self.group_angle,
        cx,
        cy,
        self.scale * self.group_scale
        )
        painter.setOpacity(1)

        # ---------- HUD слои ----------

        self.draw(painter, self.bg6, self.a6, cx, cy)
        self.draw(painter, self.bg5, self.a5, cx, cy)
        self.draw(painter, self.bg4, self.a4, cx, cy)

        self.draw(painter, self.rot3, self.r3, cx, cy)

        self.draw(painter, self.bg3, self.a3, cx, cy)

        self.draw(painter, self.rot2, self.r2, cx, cy)

        self.draw(painter, self.bg2, self.a2, cx, cy)

        self.draw(painter, self.rot1, self.r1, cx, cy)

        # индикаторы (НЕ вращаются)
        orbit = self.a2
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
