# Проект Хель

Локальный desktop-first AI-ассистент с модульным ядром, FastAPI backend и Electron frontend.

## Что внутри
- `backend/` — ядро, агенты, API, сервисы, политики и хранилище
- `frontend/` — Electron-приложение с чат-интерфейсом и переключением режимов
- `docs/architecture.md` — описание архитектуры
- `start.sh` / `start.bat` — запуск backend + frontend

## Быстрый старт
### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm start
```

## Режимы
Общий, Игровой помощник, Программист, Файловый помощник, Летописец, Репетитор,
Переводчик, Офис-менеджер, Аналитик, Ментор по коду, Трейдер,
Путешественник, Кулинар, Юрист, Системный администратор, Резервное копирование.

## Статус
Это полноценный каркас проекта: API, шина сообщений, планировщик, исполнитель,
агенты инструментов, UI и конфигурация. Некоторые интеграции работают как локальные
заглушки и могут расширяться по мере подключения внешних сервисов.
