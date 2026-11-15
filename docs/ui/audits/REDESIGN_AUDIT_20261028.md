# Jarvis Assist — Aудит и Дизайн-концепция

Дата: 2026-10-28
Аудитор: Agnes (Claude)
Статус: Предварительный, требует подтверждения перед началом работ

---

## 1. Текущее состояние

### 1.1 Технологический стек

| Слой | Технология | Детали |
|------|-----------|--------|
| Desktop-клиент | PySide6 (Qt 6) | `jarvis_ui.py`, `jarvis_hud.py`, `chat_composer.py`, `profile_dialog.py`, `toggle_switch.py`, `tech_a_animation.py` |
| Чат-интерфейс | QWebEngineView → `chat.html` | Crazy Tad донор, JS + CSS, Markdown через marked.js, DOMPurify, Lottie-эмодзи |
| Backend | Python FastAPI | `main.py`, agents (`core/agent_base.py`), LLM-сервисы, Voice runtime, Chat store |
| HUD-отрисовка | QPainter (QPixmap PNG-слои) | TECH-A скин: BG1-BG6, rotator-1/2, BigAnimation, CPU-индикатор, анимированные дуги метрик |
| Анимации | QPropertyAnimation, QTimer @16ms | Пульс START-кнопки, hover-эффекты панелей, вращение rotator-слоёв |
| Стили | Инлайн QSS (JarvisUI.apply_styles) + отдельные styleSheet() | `styles.css` есть но не используется (пустой файл 83 строки) |
| Настройки | QSettings (Windows registry) | `accent_color`, `font_family`, `window_opacity`, `glass_enabled`, профиль, чат-преференции, widget_settings |

### 1.2 Архитектура экранов

```
[Frameless Window 1280x850]
├── Header: JARVIS ASSIST | – X
├── Main (QHBoxLayout, spacing 25)
│   ├── Left panel (QVBoxLayout, width=180 + spacing)
│   │   ├── Menu QListWidget: АССИСТЕНТ / НОВЫЙ ЧАТ / ИСТОРИЯ ЧАТОВ / НАСТРОЙКИ
│   │   ├── "Закрепленные чаты" title + pinned_chats_list (fixed 120px)
│   │   ├── "Недавние" title + chats_list (fixed 120px, scrollable)
│   │   ├── Toggles card (assistant / microphone)
│   │   ├── Weather card (draggable elements)
│   │   ├── Profile card (avatar + name + username)
│   │   └── stretch
│   └── Stacked pages (QStackedWidget):
│       [0] Assistant page: JarvisHUD (710x710) + START button + label
│       [1] Chat page: QFrame#chatFrame
│       │   ├── chat_header: avatar J, title, subtitle, model combo, settings btn
│       │   ├── QWebEngineView (Crazy Tad chat HTML)
│       │   └── ChatComposer (native Qt)
│       [2] History page: history_list
│       [3] Settings page: settings_nav (list) + settings_stack (QStackedWidget)
│           ├── ОБЩИЕ (typography, colors, sound/visual, HUD opacity)
│           ├── УЧЁТНАЯ ЗАПИСЬ
│           ├── УВЕДОМЛЕНИЯ
│           ├── IRON (layers/metrics/panels inline)
│           ├── ПОГОДА
│           ├── AI (provider/model inline)
│           ├── ГОЛОС AI → перенаправляет на ОБЩИЕ
│           ├── КОМАНДЫ JARVIS (yaml reader)
│           ├── ПЕРСОНАЛИЗАЦИЯ
│           ├── КОНФИДЕНЦИАЛЬНОСТЬ
│           ├── ДАННЫЕ
│           └── ЧАТ (acrylic/avatars/timestamps/compact)
└── Floating widgets: status_widget, detached_weather, tech_action_buttons, hud_panel_buttons
```

### 1.3 Рабочие функции (нельзя нарушать)

1. **Голосовой ассистент** — START/STOP + voice runtime (backend `/voice/start`, `/voice/stop`, `/voice/status`)
2. **Микрофон** — toggle + hardware selection
3. **ТЕХ-A HUD** — рисование слоёв PNG, метрики CPU/RAM/GPU/DISK, сеть, часы/дата
4. **TECH-A кнопки** — COMP/DOCS/CTRL/DESK/XPLR/CHRM/GAME/CFG с hitbox координатами
5. **HUD панели** — верхний ряд (CHAT/AGENTS/FUNCTION/HISTORY) и нижний ряд (PROV/MOD/VID/SET/OUT)
6. **Погода** — OpenWeather API, карточка в сайдбаре и плавающая копия, визуальный редактор
7. **Текущие чаты** — Crazy Tad frontend через QWebEngine, WebChannel bridge, история сессий
8. **Composer** — вложение файлов, эмодзи/мульты, ответ, голосовая кнопка, клавиатурный Enter
9. **Смена моделей** — Ollama/Codex/Claude/FreLLMAPI через `settings/llm`
10. **Профиль** — отображение имени, username, аватар
11. **Настройки** — все диалоги сохраняются в QSettings, HUD-инлайн настройки
12. **Акцентный цвет / шрифт / прозрачность** — глобальные токены
13. **Перетаскиваемое плавающее окно статуса** voice runtime
14. **Гибкая конфигурация HUD** — слои, метрики, motion parameters

---

## 2. Основные UX/UI-проблемы

### 2.1 Критические (неприятные)

1. **Цветовой диссонанс title и акцента** — заголовок окна всегда синий `#2E89FF` независимо от accent_color пользователя, в то время как основная темаcyan `#00EBF5`. Акцент не влияет на header.
2. **Смешивание двух акцентных палитр** — `#2E89FF` (старый акцент, жёстко закодирован через `.replace("#2E89FF", accent)`) встречается параллельно с `#00EBF5` (новый cyan), создавая конфликт при стандартном cyan-акценте.
3. **Несоответствие кнопок QPushbutton** — глобальный стиль задаёт `background:#2E89FF`, `color:white`, но `dialog_stylesheet()` генерирует кнопки с `color:#071116` (тёмный текст на ярком фоне). Пользователь видит разноцветные кнопки внутри одних и тех же диалогов.
4. **Нарушение контраста на чекбоксах** — checked состояние использует `#2E89FF` (жёлто-зелёный на тёмном фоне имеет низкий контраст), плюс `dialog_stylesheet()` переопределяет на `accent_hex`, но основной stylesheet нет.
5. **Мёртвый `styles.css`** — файл существует (83 строки) но ни один компонент его не читает. В нём могут быть актуальные стили, которые потеряны.
6. **Плавает высота карточек чата** — `pinned_chats_list` фиксирован 120px (3 карточки × 36px), `chats_list` — тоже 120px. Если чатов меньше 3 — внизу пустота; если больше 3 — скролл есть только у недавних.
7. **Кнопка START (150×150)** доминирует на ассистентской странице, но визуально конфликтует с TECH-A HUD (который уже 710×710). Кнопка перекрывает центральную часть HUD вместо того чтобы быть органичной.
8. **Отсутствие состояний пустого loading/error** в чате — при отсутствии backend показывается только «Ошибка соединения» после попытки. Нет skeleton/prompt для первого запуска.

### 2.2 Средние

9. **Sidebar перегружен** — 4 раздела в фиксированной высоте 180px меню + 2 списка чатов + 2 карточки + профиль = очень тесно. `left` layout использует `addStretch()` перед карточками, но пространство ограничено шириной 180.
10. **Меню навигации** — `menu::item:hover` и `menu::item:selected` используют одинаковый синий `#2E89FF`, теряя визуальное различие. Текст на синем фоне `color:white` при selected, но при hover `color:white` — оба белые на синем, разница только в фокусе (который отключён `outline:none`).
11. **Settings header позиционируется абсолютно** — три QLabel за пределами `settings_page_widget`, спозиционированы вручную в `position_settings_header()`. При изменении размеров окна это «плывёт».
12. **History page минималистична** — только список и кнопка обновления, без превью последнего сообщения или даты.
13. **Профиль чата (JarvisChatProfileDialog)** — показывает только имя «JARVIS CHAT» и системный промпт, без информации о модели, статусе провайдера, истории.
14. **Команды Jarvis** — кнопка «ДОБАВИТЬ СВОЮ КОМАНДУ» открывает generic GlassPreferencesDialog без контекста.
15. **Текст assistant_label** — ограничен 42px высоты и 710px ширины, длинные сообщения об ошибках обрезаются.
16. **Нет индикатора состояния voice** на HUD кроме статуса во floating widget — пользователь не видит, слушает Jarvis или нет, пока не переведёт взгляд на статус-виджет.

### 2.3 Мелкие

17. `#chatItem` радиус 8px, но в коде `ChatItemWidget.paintEvent` рисует `border-radius: 10px` — несоответствие между styleheet и painted rect.
18. Кнопки `historyRefresh`, `settingsTileButton`, `chatSettingsBtn` имеют разные радиусы (10, 9, 7 px).
19. `ToggleSwitch` использует жёстко заданный `#00ebf5` в paintEvent при unchecked (серый `#444`), но checked — `self.accent_color`. Однако `start_animation()` не учитывает, что акцент мог измениться после инициализации (хотя `set_accent_color` вызывает `update()`, это работает).
20. Виджет статуса использует `WA_TranslucentBackground`, но у него есть фон `rgba(20,20,25,220)` — полупрозрачность не применяется (alpha=220 = 86% opacity).
21. Кнопки HUD-панелей (`hudPanelTop`, `hudPanelIcon`) — `hover` не меняет background вообще (прозрачный фон при hover). Визуально нет feedback.
22. Настройки «Голос AI» — перенаправляют на «Звук и визуал» вместо отдельной страницы; пользователь не понимает, почему.
23. Настройки «Учётная запись» — кнопка «ОТКРЫТЬ ПРОФИЛЬ» вызывает `show_user_profile()`, но inline-поля в странице «Учётная запись» не сохраняются (отсутствуют поле сохранения).

---

## 3. Предлагаемая дизайн-концепция

### 3.1 Философия

**«Технологичная глубина, а не техно-декор»**

Текущий Jarvis выглядит как эксперимент: Tech-A HUD (rainmeter skin, 710px) соседствует с устаревшими синими кнопками (`#2E89FF`), стеклянные карточки разного радиуса, мёртвый `styles.css`. Концепция — не «перерисовать всё в один цвет», а привести к **единому цветовому решению**, где каждый элемент находится на своём месте.

### 3.2 Цветовые токены (единая палитра)

```
--bg-deep       #0B0C10      основной фон (HUD, контейнер)
--bg-surface    #131620      поверхности карточек, панелей
--bg-elevated   #1A1E2B      elevated panels, headers
--bg-glass      rgba(20,24,34,0.85)  glass fallback
--border        rgba(255,255,255,0.10) мягкая граница
--border-accent rgba(0,235,245,0.35)   акцентная граница
--accent        #00EBF5      главный акцент (cyan)
--accent-hover  #00C4D6      hover state
--accent-dim    rgba(0,235,245,0.12)  subtile glow
--text-primary  #F0F4F8      основной текст
--text-secondary rgba(180,195,210,0.85)  вторичный
--text-muted    rgba(140,155,170,0.7)    muted / hints
--success       #34D399
--warning       #FBBF24
--error         #F87171
--danger        #EF4444      close button
```

Важно: `#2E89FF` **удалить** из всех жёстких строк. Акцентный цвет пользователя остаётся единственным ярким цветом; все кнопки — из `accent_hex` и `accent_hover`.

### 3.3 Типографика

- Семейство: `var(--font-family)` (Good Times при выборе в настройках, иначе системное sans-serif)
- Заголовки страниц: 22px, 700, uppercase tracking `+1px`
- Заголовки карточек: 12px, 700, letter-spacing `1px`, цвет `text-muted`
- Основной текст: 14px, 400
- Подсказки/hint: 11–12px, цвет `text-muted`
- HUD-текст: переменный (настраивается в настройках)

### 3.4 Радиусы

| Элемент | Radius |
|---------|--------|
| Карточки чата | 10px |
| Карточки настроек | 14px |
| Dialogs / popups | 15px |
| Кнопки | 9px |
| Input fields | 8px |
| HUD-индикаторы (gauge) | 16px (радиус дуги) |
| Профиль карточка | 10px |
| Composer bar | 12px |

### 3.5 Пространственная композиция

- Левая панель расширяется до **200–220px** (сейчас 180px, тесно для списка из двух секций + карточки)
- Чат-страница получает **sticky header** с моделью и профилем
- Settings page: навигация 200px слева, контент справа, card-based layout с `max-width 780px`
- Assistant page: HUD центрирован, START-кнопка — **внутри HUD** (как сейчас), но меньшего диаметра (~100px) и с translucent фоном, не перекрывающим центр
- Weather card — компактная, не более 200px в ширину

### 3.6 Микровзаимодействия

- Hover на панели HUD: лёгкое cyan-свечение (`accent-dim`) + scale 1.03
- Hover на карточке чата: фонарь `rgba(255,255,255,0.09)` → `rgba(255,255,255,0.14)`
- Активная кнопка START: пульс (`pulse_anim`) + glow с `accent` цветом
- Loading-состояние в чате: shimmer-анимация на bubble-placeholder
- Settings: при сохранении —短暂 toast-уведомление (сейчас `assistant_label` меняет текст, но он маленький и теряется)

---

## 4. Дизайн-система: переиспользуемые компоненты

### 4.1 Компонент «Карточка» (SettingsCard / ContentCard)

Единый стиль для всех content-card в Settings:
```css
background: var(--bg-surface);
border: 1px solid var(--border);
border-radius: 14px;
padding: 16px;
```

### 4.2 Компонент «Кнопка действия» (AccentButton)

```css
background: var(--accent);
color: #071116;
border-radius: 9px;
padding: 8px 18px;
min-height: 34px;
font-weight: 600;
```
Hover: `background: var(--accent-hover)` (lighter 115%)

### 4.3 Компонент «Поле ввода» (TextField)

```css
background: rgba(255,255,255,0.12);
border: 1px solid rgba(255,255,255,0.20);
border-radius: 8px;
padding: 8px 10px;
color: var(--text-primary);
```
Focus: border-color → `var(--accent)`

### 4.4 Компонент «Переключатель» (ToggleSwitch)

Уже реализован в `toggle_switch.py`. Сохраняем, улучшаем hover-состояние (сейчас отсутствует).

### 4.5 Компонент «Навигационный пункт меню»

```css
background: transparent;
border-radius: 10px;
padding-left: 14px;
height: 44px;
color: var(--text-secondary);
```
Selected: `background: var(--accent-dim); color: var(--accent)`
Hover: `background: rgba(255,255,255,0.06)`

### 4.6 Компонент «Системное уведомление» (Toast)

Заменяет текущее `assistant_label.setText(...)`. Это будет временная панель 320×44px в правом нижнем углу контейнера.

---

## 5. План реализации по приоритетам

### Фаза 1 — Фундамент (безопасно, высокий ROI)

**Файлы:** `jarvis_ui.py`, `jarvis_hud.py`, `chat_composer.py`

1. **Убрать `#2E89FF` и `#4aa0ff`** — все замены заменить на `accent` / `accent_hover` из текущих токенов
2. **Стандартизировать радиусы кнопок** до 9px; карточки чата — 10px
3. **Синхронизировать цвет текста заголовка** с `text_color_hex` (сейчас всегда белый)
4. **Сделать акцент цвета заголовка** окна — теперь `accent_hex` вместо жёсткого `#2E89FF`
5. **Обновить `styles.css`** — перенести все повторяющиеся QSS-фрагменты из `jarvis_ui.py` в этот файл и подключать его через `loadFromFile` или `QFile`

### Фаза 2 — Каркас интерфейса

**Файлы:** `jarvis_ui.py`

6. **Расширить левую панель** с 180 до 210px, пересчитать размеры карточек
7. **Выровнять высоты чат-карточек** — pinned list и recent list использовать одинаковую высоту строки (36px)
8. **Переработать меню навигации** — unified стиль selected/hover, добавить визуальный индикатор активной секции
9. **Sticky chat header** — вынести модель и профиль в fixed bar над webview, не скроллящийся вместе с сообщениями
10. **Добавить skeleton-загрузку** в чат (при отсутствии сообщений показывать placeholder «Спросите JARVIS…»)

### Фаза 3 — Диалоги и модальные окна

**Файлы:** `jarvis_ui.py`, `profile_dialog.py`

11. **Привести все QDialog** к единому стилю (radius 15px, background glass, borders)
12. **Унифицировать кнопки в диалогах** — accent цвет из токенов, убрать `#2E89FF` fallback
13. **Улучшить профиль чата** — добавить информацию о текущей модели и провайдере
14. **Улучшить настройки «Голос AI»** — сделать отдельной страницей вместо редиректа
15. **Добавить сохранение для «Учётная запись»** — убрать кнопку «Открыть профиль», сделать inline-сохранение

### Фаза 4 — HUD и ассистентская страница

**Файлы:** `jarvis_hud.py`, `jarvis_ui.py`

16. **Уменьшить START-кнопку** с 150px до ~100px, сделать translucent, не перекрывать центр HUD
17. **Добавить индикатор voice-статуса** прямо на HUD (маленький микрофон-индикатор)
18. **Expand assistant_label** — убрать ограничение 42px высоты, позволить многострочность
19. **Tooltip и hover feedback** для HUD-panel buttons (сейчас hover невидим)
20. **Улучшить weather card** — добавить «открыть полную погоду» по клику на всю область

### Фаза 5 — Полировка и микровзаимодействия

**Файлы:** `jarvis_ui.py`, `chat_composer.py`, `jarvis_hud.py`

21. **Toast-уведомления** вместо надписи в assistant_label
22. **Loading shimmer** при отправке сообщения в чат (в composer, до получения ответа)
23. **Плавные переходы** между страницами (QStackedWidget animation)
24. **Единый scrollbar-стиль** для всех QListWidget
25. **Адаптивность**: при resize окна пересчитывать layout (сейчас жёсткие размеры фиксированы)

---

## 6. Функции, которые необходимо сохранить

1. Весь voice runtime (`/voice/start`, `/voice/stop`, `/voice/status`)
2. TECH-A HUD рендеринг (png-слои, rotator, gauge, datetime)
3. TECH-A action buttons (COMP, DOCS, CTRL, DESK, XPLR, CHRM, GAME, CFG)
4. HUD top/bottom panel buttons с перетаскиванием и калибровкой
5. Crazy Tad chat frontend (QWebEngine + chat.html)
6. Chat composer (вложения, эмодзи, reply, voice)
7. Weather card + floating weather widget + visual editor
8. Floating voice status widget
9. User profile dialog + avatar cropping
10. AI Provider dialog (Ollama, Codex, Claude, FreeLLMAPI)
11. Glass/preferences dialogs (transparency, opacity, font, accent)
12. All QSettings keys (accent_color, font_family, window_opacity, etc.)
13. Chat sessions CRUD (pin, rename, archive, delete, history)
14. Agent list dialog (Main, Planner, Executor, Critic, etc.)

---

## 7. Критерии проверки результата

| Критерий | Как проверить |
|----------|--------------|
| Цвет заголовка окна совпадает с accent_color | Изменить accent через настройки → проверить цвет title |
| Все кнопки используют accent, нет `#2E89FF` в коде | `grep "#2E89FF"` → 0 результатов |
| Радиусы кнопок единообразны (9px) | Проверить все QPushButton styleSheet |
| Чат-карточки имеют одинаковую высоту (36px) | Визуально |
| Settings header не «плывёт» при resize | Растянуть окно → проверить позиции |
| Стиль `styles.css` подключается и работает | Проверить отсутствие дублей QSS |
| START-кнопка не перекрывает центр HUD | Визуально |
| Voice status виден на HUD (микрофон-индикатор) | Запустить Jarvis, проверить индикатор |
| Плавный hover на HUD-панелях | Навести мышь на кнопки CHAT/AGENTS/etc. |
| История чатов имеет превью (дата + последнее сообщение) | Открыть историю |
| Диалоги закрываются по Escape | Тест |
| Сборка проходит без ошибок | `python frontend/jarvis_ui.py` |
| Компилляция без syntax ошибок | `compileall frontend/` |

---

## 8. Риски

| Риск | Смягчение |
|------|-----------|
| Изменение QSS сломает существующие widget object names | Использовать только class/id селекторы, не менять objectName |
| Удаление `#2E89FF` может сломать hardcode в chat.html | Проверить chat.html отдельно (CSS-переменные) |
| Изменение размеров sidebar может сломать absolute positioning HUD-кнопок | HUD-кнопки используют свойства `hitboxBaseX/Y`, позиция от окна — нет |
| Переработка chat header может сломать WebChannel bridge | Bridge работает по JS-функциям, HTML/CSS изменять только если нужно |
| Изменение размеров card layouts в settings может «разъехаться» при resize | Проверить на 1280×850 и на 1920×1080 |
| Styles.css импорт — новый механизм, может конфликтовать с inline styles | Применять после inline, через `styleSheet += "\n" + css_content` |

---

## 9. Что НЕ делать

- Не переписывать архитектуру (Qt main loop, QWebEngine, agents, voice runtime)
- Не добавлять новые Python-зависимости
- Не менять backend API контракты
- Не пересоздавать chat.html (это Crazy Tad донор, не наша зона)
- Не удалять какие-либо Settings keys
- Не удалять TECH-A PNG-слои или логику rotator
- Не менять размер HUD (710×710 фиксирован)

---

## 10. Следующий шаг

После утверждения этого плана — начать с **Фазы 1 (Фундамент)**, затем последовательно перейти к Фазам 2–5. Каждый этап фиксируется в `docs/HANDOFF.md` с точкой отката в `backups/`.
