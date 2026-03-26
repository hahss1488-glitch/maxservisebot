# maxservisebot (MAX Bot Backend)

Бэкенд бота учёта услуг, мигрированный с Telegram transport на **MAX Bot API**.

## Запуск

```bash
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```

## Регистрация webhook в MAX

1. Поднимите публичный HTTPS endpoint (`https://<host>/max/webhook`).
2. Создайте подписку MAX webhook через `POST /subscriptions`.
3. Передайте `secret` и установите тот же `MAX_WEBHOOK_SECRET` в env.
4. Входящие запросы валидируются по заголовку `X-Max-Bot-Api-Secret`.

## Основные переменные окружения

- `MAX_BOT_TOKEN` — токен бота MAX (используется в `Authorization` header).
- `MAX_API_BASE` — базовый URL API (по умолчанию `https://platform-api.max.ru`).
- `MAX_WEBHOOK_SECRET` — секрет webhook, сравнивается с заголовком `X-Max-Bot-Api-Secret`.
- `DEVICE_KEY` — ключ доступа для `POST /api/task` (опционально).
- `NOTIFY_MAX` — `1/0`, отправлять ли уведомления в MAX из `api.py`.

## HTTP endpoints

- `POST /max/webhook` — входящий webhook MAX updates (`message_created` / `message_callback`).
- `POST /api/task` — внешний API добавления услуги в активную смену.

## Примечания

- Бизнес-логика смен, машин, услуг, комбо, календаря, истории, профиля, FAQ и админки сохранена.
- Reply UX переведён на MAX inline keyboard (кнопки типа `message`/`callback`/`link`).
- Для медиа используется upload flow MAX (`/uploads`) и attachments в `/messages`.
- Callback payload поддерживает несколько форматов (`callback.payload`, `callback.data`, `callback.button.payload`).
- Если MAX не поддерживает прямой аналог операций (например, copy/pin/unpin), используется явный fallback с логированием.

_Repo sync: recreated PR after CI issue._
