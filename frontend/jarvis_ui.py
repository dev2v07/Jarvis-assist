import sys
import requests
import os

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

TECH_FONT_FILES = {
    "Good Times": "GOODTIME.ttf",
    "Imagine font": "imagine_font.ttf",
    "HandelGotD": "HandelGotD.ttf",
    "Nasalization": "nasaliza.ttf",
    "BitDust Two": "bitdust2.ttf",
}


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


# ---------------- MAIN UI ----------------

class JarvisUI(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Jarvis Assist")
        self.resize(1280, 850)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.ui_settings = QSettings("Jarvis", "Jarvis Assist")
        self.tech_font_families = self.register_tech_fonts()
        self.active_font_family = self.ui_settings.value(
            "font_family",
            self.tech_font_families.get("Good Times", "Arial"),
        )
        QApplication.instance().setFont(QFont(self.active_font_family, 10))

        self.oldPos = None
        self.setWindowOpacity(0.96)

        self.build_ui()

        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)

        self.load_weather()

        self.weather_timer = QTimer()
        self.weather_timer.timeout.connect(self.load_weather)
        self.weather_timer.start(600000)

        # hover отслеживание
        self.chats_list.setMouseTracking(True)
        self.chats_list.viewport().setMouseTracking(True)
        self.chats_list.viewport().installEventFilter(self)


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
        QApplication.instance().setFont(QFont(family, 10))
        self.ui_settings.setValue("font_family", family)


    # ---------------- HOVER MENU BUTTON ----------------

    def eventFilter(self, obj, event):

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


    # ---------------- CHAT MENU ----------------

    def chat_menu(self, pos):

        item = self.chats_list.itemAt(pos)

        if not item:
            return

        menu = QMenu(self)

        menu.setStyleSheet("""
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
        background:#2E89FF;
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

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(30, 20, 30, 20)

        # ---------- HEADER ----------

        header = QHBoxLayout()

        title = QLabel("JARVIS ASSIST")
        title.setObjectName("title")

        header.addWidget(title)
        header.addStretch()

        btn_min = QPushButton("–")
        btn_close = QPushButton("X")

        btn_min.setFixedSize(32, 32)
        btn_close.setFixedSize(32, 32)

        btn_close.setObjectName("closeBtn")

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

        left.addWidget(self.menu)


        # ---------- PINNED CHATS ----------

        # заголовок чатов
        chats_title = QLabel("Закрепленные чаты")
        chats_title.setStyleSheet("color:#888; font-size:12px;")

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

        t_layout = QVBoxLayout(toggles)

        row1 = QHBoxLayout()
        label1 = QLabel("Ассистент")
        label1.setStyleSheet("color:white; font-size:14px;")
        toggle1 = ToggleSwitch()

        row1.addWidget(label1)
        row1.addStretch()
        row1.addWidget(toggle1)


        row2 = QHBoxLayout()
        label2 = QLabel("Микрофон")
        label2.setStyleSheet("color:white; font-size:14px;")
        toggle2 = ToggleSwitch()

        row2.addWidget(label2)
        row2.addStretch()
        row2.addWidget(toggle2)

        t_layout.addLayout(row1)
        t_layout.addLayout(row2)


        # ---------- WEATHER ----------

        weather = QFrame()
        weather.setObjectName("miniCard")
        weather.setFixedSize(180,110)

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
        self.hud = JarvisHUD()
        self.hud.setFixedSize(JarvisHUD.HUD_SIZE, JarvisHUD.HUD_SIZE)
        self.assistant_label = QLabel("Нажмите кнопку чтобы активировать JARVIS")
        self.assistant_label.setAlignment(Qt.AlignCenter)
        self.assistant_label.setStyleSheet("color:white; font-size:16px;")
        self.assistant_label.setFixedHeight(30)

        # состояние jarvis
        self.jarvis_state = False

        # кнопка jarvis
        self.jarvis_button = QPushButton("START")
        self.jarvis_button.setFixedSize(300,300)
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
        # страница настроек
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.addWidget(QLabel("НАСТРОЙКИ JARVIS"))
        settings_layout.addWidget(QLabel("Шрифт интерфейса TECH-A"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(list(self.tech_font_families.keys()))
        for index, family in enumerate(self.font_combo.itemText(i) for i in range(self.font_combo.count())):
            if self.tech_font_families.get(family) == self.active_font_family:
                self.font_combo.setCurrentIndex(index)
                break
        self.font_combo.currentTextChanged.connect(self.apply_font_family)
        settings_layout.addWidget(self.font_combo)
        settings_layout.addWidget(QLabel("Шрифты загружаются из assets/fonts, перенесённых из TECH-A/SETTINGS."))
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
color:white;
}

#menu::item:hover{
background:#2E89FF;
color:white;
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
border-radius:150px;
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

""")


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
