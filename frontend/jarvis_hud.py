import os
import math
import time
from datetime import datetime
import psutil
import GPUtil

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import (
    QPainter, QPixmap, QFont, QFontDatabase,
    QPen, QColor, QFontMetricsF
)
from PySide6.QtCore import QTimer, Qt, QRectF, QPointF
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

    def __init__(self, accent_color=None, interface_font=None, text_color=None):
        super().__init__()

        self.accent_color = QColor(accent_color or "#00ebf5")
        self.text_color = QColor(text_color or "#ffffff")

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # HUD PNG layers. Group.png is intentionally not loaded: it is the
        # blue glow layer that is absent from the original clean composition.
        self.bg1 = QPixmap(os.path.join(ASSETS, "BG1.png"))
        self.bg2 = QPixmap(os.path.join(ASSETS, "BG2.png"))
        self.bg3 = QPixmap(os.path.join(ASSETS, "BG3.png"))
        self.bg4 = QPixmap(os.path.join(ASSETS, "BG4.png"))
        self.bg5 = QPixmap(os.path.join(ASSETS, "BG5.png"))
        self.bg6 = QPixmap(os.path.join(ASSETS, "BG6.png"))

        # Rainmeter keeps these in a separate rotator config.
        self.rotator_1 = QPixmap(os.path.join(ROTATOR, "1xx.png"))
        self.rotator_2 = QPixmap(os.path.join(ROTATOR, "2x.png"))
        self.big_animation = QPixmap(os.path.join(ASSETS, "BigAnimation.png"))

        self.scale = self.HUD_SIZE / self.bg6.width()
        self.setFixedSize(self.HUD_SIZE, self.HUD_SIZE)
        self.render_dpr = max(1.0, float(self.devicePixelRatioF()))

        # Compose the native Rainmeter image meters once at the physical
        # screen resolution. This avoids a second Qt/DWM resample on 125% DPI.
        self.static_bg = self.build_static_bg()

        # Optional motion is isolated from static BG1-BG6 composition.
        self.animation = TechAAnimation()
        self.gauge_bg = self.bg1.scaled(
            self.GAUGE_BG_SIZE,
            self.GAUGE_BG_SIZE,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        # реальные данные
        self.cpu = self.ram = self.gpu = self.disk = 0
        self.temp = 0
        self.net = 0.0
        self.net_display = "0K"
        self.net_readouts = ("0 B", "0 B", "0 B", "0 B")
        self.net_upload_rate = 0.0
        self.net_download_rate = 0.0
        self.net_upload_progress = 0.0
        self.net_download_progress = 0.0
        self.clock_text = "00:00"
        self.date_text = "01ST JAN"
        self.update_datetime()
        self.ram_total_gb = 0.0
        self._net_previous = psutil.net_io_counters()
        self._net_previous_at = time.monotonic()

        # плавная анимация
        self.cpu_anim = self.ram_anim = self.gpu_anim = self.disk_anim = 0
        self.temp_anim = self.net_anim = 0

        # шрифт
        font_path = os.path.join(FONTS, "GOODTIME.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        family = QFontDatabase.applicationFontFamilies(font_id)[0]

        ram_font_path = os.path.join(FONTS, "bitdust2.ttf")
        ram_font_id = QFontDatabase.addApplicationFont(ram_font_path)
        ram_families = QFontDatabase.applicationFontFamilies(ram_font_id)
        ram_family = ram_families[0] if ram_families else family

        self.font_big = QFont(family, 10)
        self.font_label = QFont(family, 7)
        # Original BitDust readout, enlarged by 2.3 px for readability.
        self.font_ram = QFont(ram_family, 8.3)
        self.font_net = QFont(ram_family, 8.3)
        self.font_time = QFont(ram_family, 14.3)
        if interface_font:
            self.set_interface_font(interface_font)

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
        self.ram_total_gb = psutil.virtual_memory().total / (1024 ** 3)

        try:
            gpus = GPUtil.getGPUs()
            self.gpu = int(gpus[0].load * 100) if gpus else 0
        except:
            self.gpu = 0

        self.disk = int(psutil.disk_usage('C:/').percent)
        self.temp = self.read_max_temperature()

        now = time.monotonic()
        counters = psutil.net_io_counters()
        elapsed = max(0.1, now - self._net_previous_at)
        sent_delta = max(0, counters.bytes_sent - self._net_previous.bytes_sent)
        recv_delta = max(0, counters.bytes_recv - self._net_previous.bytes_recv)
        self.net_upload_rate = sent_delta / elapsed
        self.net_download_rate = recv_delta / elapsed
        transferred = sent_delta + recv_delta
        # NET is displayed as combined throughput in Mbps, capped at 100
        # so it remains compatible with the gauge's percentage arc.
        net_mbps = max(0.0, transferred * 8 / elapsed / 1_000_000)
        self.net = min(100.0, net_mbps)
        self.net_display = (
            f"{net_mbps * 1000:.0f}K" if net_mbps < 1.0
            else f"{net_mbps:.1f}"
        )
        self.net_readouts = (
            self.format_bytes(counters.bytes_sent - self._net_previous.bytes_sent),
            self.format_bytes(counters.bytes_sent),
            self.format_bytes(counters.bytes_recv),
            self.format_bytes(counters.bytes_recv - self._net_previous.bytes_recv),
        )
        self._net_previous = counters
        self._net_previous_at = now

    @staticmethod
    def format_bytes(value):
        value = max(0, float(value))
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{value:.1f} {unit}"
            value /= 1024

    @staticmethod
    def read_max_temperature():
        """Return the highest available CPU/GPU temperature in Celsius."""
        temperatures = []
        try:
            for entries in psutil.sensors_temperatures(fahrenheit=False).values():
                temperatures.extend(
                    reading.current for reading in entries
                    if reading.current is not None
                )
        except (AttributeError, OSError):
            pass
        try:
            temperatures.extend(
                gpu.temperature for gpu in GPUtil.getGPUs()
                if gpu.temperature is not None
            )
        except (AttributeError, OSError):
            pass
        return int(round(max(temperatures))) if temperatures else 0

    def animate(self):

        # Match Rainmeter's separate timing: rotator Update=50ms and the
        # main skin's BigAnimation frame update=1000ms.
        self.animation.step(16.0)

        # Показатели движутся по той же орбитальной оси, что и кольца TECH-A.
        # Значение a2 уже является частью существующей рабочей анимации.
        self.cpu_anim += (self.cpu - self.cpu_anim) * 0.08
        self.ram_anim += (self.ram - self.ram_anim) * 0.08
        self.gpu_anim += (self.gpu - self.gpu_anim) * 0.08
        self.disk_anim += (self.disk - self.disk_anim) * 0.08
        self.temp_anim += (self.temp - self.temp_anim) * 0.08
        self.net_anim += (self.net - self.net_anim) * 0.08
        # Match the original TECH-A CalcNet formulas:
        # NetIn / 6144000 and NetOut / 1048576.
        self.net_upload_progress += (
            min(1.0, self.net_upload_rate / 1048576.0) - self.net_upload_progress
        ) * 0.16
        self.net_download_progress += (
            min(1.0, self.net_download_rate / 6144000.0) - self.net_download_progress
        ) * 0.16
        self.update_datetime()

        self.update()

    def update_datetime(self):
        """Synchronize the HUD clock and date with the local PC time."""
        current = datetime.now()
        self.clock_text = current.strftime("%H:%M")
        day = current.day
        if 10 <= day % 100 <= 20:
            suffix = "TH"
        else:
            suffix = {1: "ST", 2: "ND", 3: "RD"}.get(day % 10, "TH")
        self.date_text = f"{day:02d}{suffix} {current.strftime('%b').upper()}"

    def set_accent_color(self, color):
        """Update the active indicator color without rebuilding the HUD."""
        parsed = QColor(color)
        if parsed.isValid():
            self.accent_color = parsed
            self.update()

    def set_interface_font(self, family):
        """Apply the selected application font to every HUD text meter."""
        if not family:
            return
        self.font_big = QFont(family, 10)
        self.font_label = QFont(family, 7)
        self.font_ram = QFont(family, 8.3)
        self.font_net = QFont(family, 8.3)
        self.font_time = QFont(family, 14.3)
        self.update()

    def set_text_color(self, color):
        """Update the color of all live text drawn by the HUD."""
        parsed = QColor(color)
        if parsed.isValid():
            self.text_color = parsed
            self.update()

    def ring_pos(self, cx, cy, angle):

        r = self.GAUGE_RADIUS

        x = cx + r * math.cos(math.radians(angle))
        y = cy + r * math.sin(math.radians(angle))

        return x, y

    def build_static_bg(self):
        pixel_size = round(self.HUD_SIZE * self.render_dpr)
        canvas = QPixmap(pixel_size, pixel_size)
        canvas.setDevicePixelRatio(self.render_dpr)
        canvas.fill(Qt.transparent)
        composer = QPainter(canvas)
        composer.setRenderHint(QPainter.Antialiasing, False)
        for pixmap in (self.bg1, self.bg2, self.bg3, self.bg4, self.bg5, self.bg6):
            if not pixmap.isNull():
                if self.render_dpr == 1.0:
                    layer = pixmap
                else:
                    layer = pixmap.scaled(
                        pixel_size,
                        pixel_size,
                        Qt.IgnoreAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    layer.setDevicePixelRatio(self.render_dpr)
                composer.drawPixmap(0, 0, layer)
        composer.end()
        return canvas

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        cx = self.width() / 2
        cy = self.height() / 2

        # ---------- HUD слои ----------

        # Native 1:1 raster cache; no per-frame scaling or smoothing.
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.drawPixmap(0, 0, self.static_bg)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self.animation.big_animation_enabled:
            self.draw_big_animation(painter)

        # GAME MODE deactivates the Rainmeter rotator layers. The 3x layer is
        # intentionally removed; only the first two rotators remain active.
        if self.animation.rotator_visible:
            self.draw_rotator(painter, self.rotator_1, self.animation.rotator_1, cx, cy)
            self.draw_rotator(painter, self.rotator_2, self.animation.rotator_2, cx, cy)

        self.draw_datetime(painter)

        # индикаторы (НЕ вращаются)
        # Match the original TECH-A repeated cell layout.  The source skin
        # places six cells around the ring. Four values are live; two cells
        # remain intentionally empty as reserved module slots.
        cpu_x, cpu_y = 80, 250
        gpu_x, gpu_y = 80, 465
        disk_x, disk_y = 645, 465
        ram_x, ram_y = 645, 250
        self.draw_net_readouts(painter)
        self.draw_net_progress(painter)
        self.draw_gauge(painter, cpu_x, cpu_y, self.cpu_anim, "CPU")
        self.draw_gauge(painter, ram_x, ram_y, self.ram_anim, "RAM")
        self.draw_gauge(painter, gpu_x, gpu_y, self.gpu_anim, "GPU")
        self.draw_gauge(painter, disk_x, disk_y, self.disk_anim, "DISK")
        self.draw_ram_panel(painter)

    def draw_datetime(self, painter):
        """Render local 24-hour time above and ordinal date below the HUD."""
        painter.save()
        painter.setFont(self.font_time)
        color = QColor(self.text_color)
        color.setAlpha(225)
        painter.setPen(color)
        time_metrics = QFontMetricsF(self.font_time)

        # The user-selected placement is the first outer ring, BG6, on the
        # vertical center axis rather than the original inner MeterTime anchors.
        time_width = time_metrics.horizontalAdvance(self.clock_text)
        painter.drawText(QPointF(355 - time_width / 2, 61), self.clock_text)

        painter.setFont(self.font_net)
        metrics = QFontMetricsF(self.font_net)
        day_part, month_part = self.date_text.split(" ", 1)
        day_width = metrics.horizontalAdvance(day_part)
        month_width = metrics.horizontalAdvance(month_part)
        date_center_x = 363  # +8 px from the centered source alignment.
        painter.drawText(QPointF(date_center_x - (day_width + month_width + 6) / 2, 660), day_part)
        painter.drawText(QPointF(date_center_x + (day_width + 6 - month_width) / 2, 660), month_part)
        painter.restore()

    def draw_big_animation(self, painter):
        if self.big_animation.isNull():
            return
        frame_width = self.big_animation.width() // 10
        frame = self.big_animation.copy(
            self.animation.big_animation_frame * frame_width,
            0,
            frame_width,
            self.big_animation.height(),
        )
        if self.render_dpr != 1.0:
            frame = frame.scaled(
                round(self.HUD_SIZE * self.render_dpr),
                round(self.HUD_SIZE * self.render_dpr),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
            frame.setDevicePixelRatio(self.render_dpr)
        painter.drawPixmap(0, 0, frame)

    def draw_net_readouts(self, painter):
        """Render the original UPLOAD/DOWNLOAD readouts at source anchors."""
        painter.save()
        painter.setFont(self.font_net)
        # The source BG layer already contains the UP/DN labels; draw values only.
        primary = QColor(self.text_color)
        primary.setAlpha(220)
        secondary = QColor(self.text_color)
        secondary.setAlpha(190)
        readouts = (
            (self.net_readouts[0], 60, 315, primary),
            (self.net_readouts[1], 60, 335, secondary),
            (self.net_readouts[2], 60, 365, secondary),
            (self.net_readouts[3], 60, 385, primary),
        )
        for value, x, y, color in readouts:
            painter.setPen(color)
            painter.drawText(QRectF(x - 32, y, 64, 14), Qt.AlignCenter, value)
        painter.restore()

    def draw_net_progress(self, painter):
        """Render the two live network progress arcs from the TECH-A NET meters."""
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        center_x, center_y = self.width() / 2, self.height() / 2
        radius = 263.0
        rect = QRectF(
            center_x - radius,
            center_y - radius,
            radius * 2,
            radius * 2,
        )

        # Original source: CalcNetOut has a -0.3665 radian sweep and
        # CalcNetIn has a +0.3665 radian sweep around the left side.
        upload_color = QColor(self.accent_color)
        upload_color.setAlpha(220)
        pen = QPen(upload_color, 2.0, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 179 * 16, round(-21 * 16 * self.net_upload_progress))

        download_color = QColor(self.accent_color)
        download_color.setAlpha(210)
        pen.setColor(download_color)
        painter.setPen(pen)
        painter.drawArc(rect, 181 * 16, round(21 * 16 * self.net_download_progress))
        painter.restore()

    def draw_rotating_pixmap(self, painter, pixmap, angle, cx, cy):
        if pixmap.isNull():
            return
        painter.save()
        painter.translate(round(cx), round(cy))
        painter.rotate(angle)
        painter.drawPixmap(-pixmap.width() // 2, -pixmap.height() // 2, pixmap)
        painter.restore()

    def draw_rotator(self, painter, pixmap, angle, cx, cy):
        if pixmap.isNull():
            return
        self.draw_rotating_pixmap(painter, pixmap, angle, cx, cy)

    def draw_rotator_at(self, painter, pixmap, angle, x, y):
        if pixmap.isNull():
            return
        painter.save()
        painter.translate(round(x + pixmap.width() / 2), round(y + pixmap.height() / 2))
        painter.rotate(angle)
        painter.drawPixmap(-pixmap.width() // 2, -pixmap.height() // 2, pixmap)
        painter.restore()

    def draw_gauge(self, painter, x, y, value, label, display_text=None):

        painter.save()

        # BG1 под индикатор
        painter.drawPixmap(
            int(x - self.gauge_bg.width() / 2),
            int(y - self.gauge_bg.height() / 2),
            self.gauge_bg
        )

        rect = QRectF(x - 16, y - 16, 30, 30)

        # подпись
        painter.setPen(self.text_color)
        painter.setFont(self.font_label)
        painter.drawText(x - 14, y - 20, label)

        # фон дуги
        pen_bg = QPen(QColor(120, 120, 120), 2)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 135 * 16, 270 * 16)

        # дуга нагрузки
        pen_val = QPen(self.accent_color, 3)
        painter.setPen(pen_val)

        span = int(-value * 270 / 100 * 16)
        painter.drawArc(rect, 135 * 16, span)

        # процент
        painter.setPen(self.text_color)
        painter.setFont(self.font_big)
        painter.drawText(rect, Qt.AlignCenter, display_text or f"{int(value)}")

        painter.restore()

    def draw_ram_panel(self, painter):
        """Render the original TECH-A RAM side readout and arc pair."""
        used = max(0.0, min(100.0, float(self.ram_anim)))
        free = 100.0 - used
        total = self.ram_total_gb or (psutil.virtual_memory().total / (1024 ** 3))

        painter.save()

        # Original text meters: freeRAM.p2x2, UsedTOTAL, UsedRAM.p2x.
        painter.setFont(self.font_ram)
        secondary = QColor(self.text_color)
        secondary.setAlpha(220)
        painter.setPen(secondary)
        painter.drawText(QRectF(625, 302, 60, 18), Qt.AlignCenter, f"{free:.2f}%")
        painter.setPen(self.text_color)
        painter.drawText(QRectF(625, 342, 70, 18), Qt.AlignCenter, f"{total:.2f} G")
        painter.setPen(secondary)
        painter.drawText(QRectF(625, 382, 60, 18), Qt.AlignCenter, f"{used:.2f}%")

        # Original RAMl12x/RAMl12xx values are short ROUNDLINE arcs.
        rect = QRectF(361 - 264, 355 - 264, 528, 528)
        full_span = int(21 * 16)

        painter.setPen(QPen(QColor(255, 255, 255, 85), 3))
        painter.drawArc(rect, 1 * 16, full_span)
        ram_glow = QColor(self.accent_color)
        ram_glow.setAlpha(70)
        painter.setPen(QPen(ram_glow, 3))
        painter.drawArc(rect, 359 * 16, -full_span)

        used_span = max(1, int(full_span * used / 100.0))
        free_span = max(1, int(full_span * free / 100.0))
        painter.setPen(QPen(QColor(255, 255, 255, 220), 4))
        painter.drawArc(rect, 1 * 16, used_span)
        ram_value = QColor(self.accent_color)
        ram_value.setAlpha(220)
        painter.setPen(QPen(ram_value, 4))
        painter.drawArc(rect, 359 * 16, -free_span)

        painter.restore()
