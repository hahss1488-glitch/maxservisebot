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

### Автообновление webhook (рекомендуется для туннелей)

Если туннельный URL меняется (например, после перезапуска), используйте единый entrypoint:

```bash
/root/maxservisebot/upmsb
```

Execution path:
- `upmsb` — главный entrypoint для ручного запуска/cron/systemd.
- `scripts/run_tunnel_and_update_webhook.sh` — orchestrator (получает URL туннеля, пишет `current_tunnel_url.txt`).
- `scripts/update_max_webhook.py` — helper синка MAX subscriptions (GET -> DELETE -> POST -> verify=1).

Workflow:
- при необходимости запускает туннель (`TUNNEL_START_CMD`),
- извлекает актуальный публичный URL (из `MAX_TUNNEL_URL`/`TUNNEL_URL`/`...` или `TUNNEL_STATUS_URL`),
- сохраняет URL в `CURRENT_TUNNEL_URL_FILE` (по умолчанию `/root/maxservisebot/current_tunnel_url.txt`),
- запускает `scripts/update_max_webhook.py`, который:
- получает текущие подписки (`GET /subscriptions`),
- удаляет старые (`DELETE /subscriptions?url=...`),
- создаёт одну новую подписку на текущий URL (`POST /subscriptions`),
- проверяет, что осталась ровно одна активная подписка.

## Основные переменные окружения

- `MAX_BOT_TOKEN` — токен бота MAX (используется в `Authorization` header).
- `MAX_API_BASE` — базовый URL API (по умолчанию `https://platform-api.max.ru`).
- `MAX_WEBHOOK_SECRET` — секрет webhook, сравнивается с заголовком `X-Max-Bot-Api-Secret`.
- `MAX_WEBHOOK_URL` / `WEBHOOK_URL` — полный URL webhook (например, `https://.../max/webhook`).
- `MAX_TUNNEL_URL` / `TUNNEL_URL` / `WEBHOOK_BASE_URL` / `PUBLIC_BASE_URL` — базовый URL туннеля, если полный `.../max/webhook` не передаётся.
- `CURRENT_TUNNEL_URL_FILE` — абсолютный путь до файла с последним tunnel URL (по умолчанию `/root/maxservisebot/current_tunnel_url.txt`).
- `MAXSERVISEBOT_HOME` — корень проекта на сервере (по умолчанию `/root/maxservisebot`).
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
