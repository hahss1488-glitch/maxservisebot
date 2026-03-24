# Техническая спецификация миграции `maxservisebot`: Telegram -> MAX (этап анализа)

## 1) Краткое summary текущей архитектуры репозитория

- Основной runtime бота — монолит `bot.py` на `python-telegram-bot` (Application + handlers + polling).  
- Персистентный слой — `database.py` (SQLite, ручные schema-migrations через `PRAGMA table_info` + `ALTER TABLE`).  
- Внешний HTTP ingress — `api.py` (`FastAPI`, endpoint `/api/task`) с прямой отправкой в Telegram Bot API (`https://api.telegram.org/bot.../sendMessage`).  
- UI/рендеринг — inline/reply клавиатуры + Pillow-рендеры dashboard/leaderboard.  
- Состояние диалога — в `context.user_data` (FSM-флаги + временные payload).  
- Фоновая автоматизация — `application.job_queue` (daily/repeating jobs: отчёты/подписки/напоминания о закрытии смен).  

---

## 2) Таблица Telegram-specific зависимостей (инвентаризация)

> Формат: **Категория | Файл/функция | Telegram-сущность | Зачем используется | Целевая замена в MAX**

| Категория | Файл/функция | Telegram-сущность | Текущее назначение | Целевая замена в MAX |
|---|---|---|---|---|
| bootstrap/startup | `bot.py::main()` | `Application.builder().token(...).build()`, `run_polling(Update.ALL_TYPES)` | Инициализация и запуск long polling в Telegram | MAX transport: webhook в prod (`POST /subscriptions`) и long polling в dev (`GET /updates`) |
| handlers registry | `bot.py::main()` | `CommandHandler`, `MessageHandler`, `CallbackQueryHandler` | Маршрутизация `/start`, текста, callback-кнопок | Свой dispatcher по `update_type` (`message_created`, `message_callback`) |
| update model | почти все handler-функции `bot.py` | `Update`, `update.effective_user`, `update.message`, `update.callback_query` | Доступ к пользователю/сообщению/кнопкам | MAX `Update` object (`update_type`, `timestamp`, `message`, `user_locale`) + `callback` для callback-событий |
| callback handling | `bot.py::handle_callback()` | `CallbackQuery`, `query.data`, `query.answer()`, `query.edit_message_text()` | Кнопочная навигация и вызов бизнес-веток | MAX `message_callback` + `callback_id`; подтверждение через `POST /answers` |
| exact callback routing | `bot.py::dispatch_exact_callback()` | exact `callback_data` routes | Точечные команды кнопок | Сохранить payload-словарь 1:1, доставлять как payload callback-кнопки MAX |
| prefix callback routing | `bot.py::handle_callback()` (`prefix_handlers`) | prefix-based parsing `query.data.startswith(...)` | Параметризованные маршруты (`service_`, `calendar_`, `admin_`...) | Сохранить схему payload, парсить `callback.payload` MAX |
| inline keyboard | множественные `build_*_keyboard`, `InlineKeyboardMarkup`, `InlineKeyboardButton` | inline-кнопки под сообщением | Основной UX и навигация | MAX attachment `type=inline_keyboard`, кнопки `callback/link/...` |
| reply keyboard | `create_main_reply_keyboard`, `create_tools_reply_keyboard` | `ReplyKeyboardMarkup`, `KeyboardButton` | Быстрое меню внизу чата | В MAX подтверждена inline-клавиатура; reply-клавиатура = unknown, нужен UX-редизайн на inline |
| context state | множественные места `context.user_data` | in-memory per-user dict | FSM и временные флаги/буферы | Выделить state-storage слой (in-memory + DB для критичных ключей) |
| send message | `reply_text`, `context.bot.send_message` | Telegram sendMessage | Ответы, системные уведомления, рассылки | `POST /messages` с `user_id/chat_id` + `NewMessageBody` |
| edit message | `query.edit_message_text`, `context.bot.edit_message_text` | Telegram editMessageText | Обновление экранов/меню | `PUT /messages` (подтверждён метод, параметры требуют финального закрепления) |
| delete message | `context.bot.delete_message` | Telegram deleteMessage | Удаление старого pin/служебных сообщений | `DELETE /messages` (ограничение MAX: < 24ч) |
| pin/unpin | `pin_chat_message`, `unpin_chat_message` | Telegram pin API | Закрепление цели смены | В MAX есть чатовые методы pin/unpin (нужно уточнение прав/параметров под bot scope) |
| media upload/download | `_refresh_telegram_avatar_cache`, `_consume_profile_avatar_upload`, FAQ media | `get_user_profile_photos`, `get_file`, `file_id`, `send_photo`, `send_video`, `copy_message`, `reply_document` | Аватары, FAQ-видео, отчёты, dashboard/leaderboard image | MAX upload flow через `POST /uploads` + затем attachment token в `POST /messages` |
| answer callback | `handle_callback` (`await query.answer()`) | `answerCallbackQuery` semantics | Закрытие spinner/ack на клик | `POST /answers?callback_id=...` (+ optional notification/message) |
| scheduler | `on_startup`, `job_queue.run_daily/run_repeating` | PTB JobQueue | Периодические отчёты/уведомления | Отдельный scheduler процесс/таск (APScheduler/Cron/worker), независимый от PTB |
| identity in DB | `database.py users.telegram_id`, banned/users lookups | telegram user id как primary external key | Идентификация пользователей | Миграция на MAX `user_id` (минимально-разрушительно: `platform_user_id` + `platform`) |
| api.py dependency | `api.py::maybe_notify_telegram`, `TaskPayload.chat_id` | прямой HTTP к Telegram Bot API | нотификация после `/api/task` | MAX sender adapter + поле `user_id/chat_id` MAX и/или совместимый алиас |

---

## 3) Таблица сущностей MAX (только подтверждённые факты + unknown)

| Сущность | Подтверждённые поля/параметры | Что достоверно | Unknown / проверить | Telegram-аналог |
|---|---|---|---|---|
| Transport base | `https://platform-api.max.ru` | Единый API домен MAX | Нет | `api.telegram.org` |
| Auth model | HTTP header `Authorization: <token>` | Query-token deprecated | Ротация/TTL токена — вне текущего scope | `Authorization: Bearer`/bot token в URL (Telegram) |
| Update delivery | Webhook (`POST /subscriptions`) и long polling (`GET /updates`) | Prod рекомендован webhook; dev/test — long polling | Требуемая стратегия ack/повторов при 5xx | Telegram webhook/getUpdates |
| Webhook security | `secret` в подписке, входящий header `X-Max-Bot-Api-Secret` | Можно верифицировать источник | Политика повторной доставки и таймаут retry | Telegram secret token webhook |
| Webhook SLA | endpoint должен вернуть `HTTP 200` до 30 секунд | Зафиксировано | Подробности retry backoff | Telegram webhook timeout |
| Update object | `update_type`, `timestamp`, `message`, `user_locale` | Базовая структура известна | Полный список `update_type` для проекта | Telegram `Update` |
| Message events | минимум `message_created`, `message_callback` | Достаточно для текущего UX бота | Нужны ли доп. типы (edited/deleted/etc) | `message`, `callback_query` |
| GET /updates | `types=message_created,message_callback`, `limit`, `timeout`, `marker` | Есть фильтрация типов и long polling marker | Семантика marker при конкурирующих consumer | Telegram getUpdates offset/timeout |
| Message object | `sender`, `recipient`, `timestamp`, `link`, `body`, `stat`, `url` | Базовый объект сообщения подтверждён | Полная схема `stat/url/link` в edge-кейсах | Telegram `Message` |
| Send message | `POST /messages` + query `user_id`/`chat_id` + body `NewMessageBody` | Отправка подтверждена | Приоритет, если переданы оба (`user_id`+`chat_id`) | `sendMessage` |
| NewMessageBody | `text`, `attachments`, `link`, `notify`, `format` | `format` = `markdown/html`; `notify` bool | Ограничения по markdown/html subset | Telegram parse_mode + reply_markup + disable_notification |
| Keyboard model | attachment `type=inline_keyboard` | Inline keyboard подтверждена | Есть ли reply keyboard аналог | Telegram InlineKeyboardMarkup |
| Button types | `callback`, `link`, `request_contact`, `request_geo_location`, `open_app`, `message` | Все перечисленные типы документированы | Лимиты payload per button | Telegram InlineKeyboardButton types |
| Callback handling | update `message_callback`, callback id в `updates[i].callback.callback_id` | Callback id подтверждён | Полная callback schema (payload path) | Telegram CallbackQuery |
| Callback answer | `POST /answers?callback_id=...`, body: `message`/`notification` | ACK + optional UI response | Можно ли только ACK без тела (по факту да/нет) | Telegram `answerCallbackQuery` (+ edit message flow) |
| Edit message | `PUT /messages` (метод есть) | Наличие метода подтверждено | Точные параметры идентификации сообщения/ограничения | Telegram editMessage* |
| Delete message | `DELETE /messages` | Наличие метода подтверждено; удаление <24ч | Поведение для старых сообщений/прав бота | Telegram deleteMessage |
| Upload/media | `POST /uploads` + token для attachments в сообщении | Отдельный upload flow подтверждён | Поддерживаемые MIME/size limits и lifecycle token | Telegram sendPhoto/sendDocument + file_id reuse |
| Rate limits/errors | 30 rps; HTTP 200/400/401/404/405/429/503 | Общая матрица кодов подтверждена | Retry policy per code (особенно 429/503) | Telegram flood limits + HTTP errors |
| Identity/addressing | отправка на `user_id` или `chat_id` | addressing подтверждён | Отличия `sender.user_id` vs `recipient.chat_id` в приват/группе | Telegram user_id/chat_id |

---

## 4) Telegram -> MAX mapping (по коду проекта)

| Telegram (в проекте) | MAX соответствие | Примечание для миграции |
|---|---|---|
| `Application.run_polling` | `GET /updates` (dev) или webhook subscription (prod) | Для prod убрать polling runtime |
| `Update` | `Update` (`update_type` + payload) | Ввести adapter: normalize входные обновления |
| `update.message` text flow | `message_created` + `message.body.text` | Переписать парсер входа на MAX schema |
| `CallbackQuery` | `message_callback` + `callback` object | Унифицировать callback extractor |
| `query.data` | callback button `payload` | Payload-формат можно сохранить почти 1:1 |
| `InlineKeyboardMarkup` | attachment `{type:inline_keyboard,payload.buttons}` | Генераторы клавиатур переписать в MAX-json |
| `InlineKeyboardButton(callback_data=...)` | button `{type:"callback", payload:"..."}` | Учитывать лимиты/валидацию payload |
| `InlineKeyboardButton(url=...)` | button `{type:"link", url:"..."}` | Прямой аналог |
| `ReplyKeyboardMarkup` | **unknown native** | Заменять на inline-меню/кнопки-сообщения |
| `reply_text` | `POST /messages` (`text`) | Нужен recipient resolver |
| `query.edit_message_text` | `PUT /messages` | Требует adapter message identity |
| `context.bot.delete_message` | `DELETE /messages` | Учитывать <24h ограничение |
| `query.answer()` | `POST /answers` | Для callback UX обязательный ACK path |
| `send_photo/send_video/send_document` | `POST /uploads` -> attachment token -> `POST /messages` | Нужен upload adapter + media mapper |
| Telegram `file_id` reuse | MAX upload token / media id | Семантика кэша другая, нужен слой абстракции |
| `context.user_data` | app state store | Критичное состояние перенести в DB |
| `telegram user.id` | MAX `user_id` | DB identity migration |
| `chat_id` telegram | MAX `chat_id`/`user_id` | В API оставить backward-compatible alias |
| `job_queue` | отдельный scheduler | Фоновые задачи отвязать от PTB Application |

---

## 5) Callback routes (карта маршрутов)

### 5.1 Exact callbacks (63)

`open_shift`, `add_car`, `current_shift`, `refresh_dashboard`, `history_0`, `settings`, `change_decade_goal`, `calendar_rebase`, `leaderboard`, `export_csv`, `backup_db`, `reset_data`, `reset_data_yes`, `reset_data_no`, `toggle_price`, `toggle_images_mode`, `combo_settings`, `combo_create_settings`, `admin_panel`, `admin_users`, `admin_banned_users`, `admin_subscriptions`, `admin_broadcast_menu`, `admin_broadcast_all`, `admin_broadcast_expiring_1d`, `admin_broadcast_expired`, `admin_broadcast_pick_user`, `admin_broadcast_cancel`, `faq`, `nav_shift`, `nav_navigator`, `nav_history`, `nav_tools`, `nav_help`, `subscription_info`, `subscription_info_photo`, `account_info`, `profile_change_name`, `profile_avatar_upload`, `profile_avatar_reset`, `profile_change_rank_prefix`, `show_price`, `calendar_open`, `nav:back`, `admin_faq_menu`, `admin_media_menu`, `admin_media_set_profile`, `admin_media_set_leaderboard`, `admin_media_clear_profile`, `admin_media_clear_leaderboard`, `admin_faq_set_text`, `admin_faq_set_video`, `admin_faq_preview`, `admin_faq_clear_video`, `admin_faq_topics`, `admin_faq_topic_add`, `admin_faq_cancel`, `combo_builder_save`, `history_decades`, `back`, `cleanup_data`, `cancel_add_car`, `noop`.

### 5.2 Prefix callbacks (56)

`service_page_`, `toggle_price_car_`, `repeat_prev_`, `service_search_`, `search_text_`, `search_cancel_`, `combo_menu_`, `combo_apply_`, `combo_save_from_car_`, `combo_delete_prompt_`, `combo_delete_confirm_`, `combo_edit_`, `combo_rename_`, `childsvc_`, `back_to_services_`, `service_`, `clear_`, `confirm_clear_`, `save_`, `shift_repeats_`, `combo_builder_toggle_`, `admin_user_`, `admin_sub_user_`, `admin_toggle_block_`, `admin_toggle_leaderboard_`, `admin_toggle_broadcast_`, `admin_activate_month_`, `admin_activate_days_prompt_`, `admin_disable_subscription_`, `admin_broadcast_user_`, `admin_unban_`, `calendar_nav_`, `calendar_day_`, `calendar_set_`, `calendar_back_month_`, `calendar_setup_pick_`, `calendar_setup_save_`, `calendar_edit_toggle_`, `faq_topic_`, `admin_faq_topic_edit_`, `admin_faq_topic_del_`, `history_decades_page_`, `history_decade_`, `history_day_`, `history_edit_car_`, `cleanup_month_`, `cleanup_day_`, `day_repeats_`, `delcar_`, `delday_prompt_`, `delday_confirm_`, `toggle_edit_`, `close_confirm_yes_`, `close_confirm_no_`, `close_`.

### 5.3 Формат payload и перенос в MAX

- Сейчас payload — строковый DSL (`prefix_part1_part2...`), парсится через `replace/split` в callback-обработчиках.  
- Для MAX: сохранить тот же формат строки как `callback.payload`; transport сменится, бизнес-логика парсинга останется.  
- Рекомендация этапа: сначала 1:1 перенос payload grammar, затем (после стабилизации) нормализация формата.  

---

## 6) State/session: ключи `context.user_data` и сценарии

### 6.1 Выявленные ключи

`admin_user_back`, `awaiting_admin_broadcast`, `awaiting_admin_faq_text`, `awaiting_admin_faq_topic_add`, `awaiting_admin_faq_topic_edit`, `awaiting_admin_faq_video`, `awaiting_admin_section_photo`, `awaiting_admin_subscription_days`, `awaiting_car_number`, `awaiting_combo_name`, `awaiting_combo_rename`, `awaiting_decade_goal`, `awaiting_distance`, `awaiting_goal`, `awaiting_profile_avatar`, `awaiting_profile_name`, `awaiting_profile_rank_prefix`, `awaiting_service_search`, `calendar_edit_mode`, `calendar_month`, `calendar_setup_days`, `combo_builder`, `current_car`, `history_decades_page`, `price_mode`, `search_chat_id`, `search_message_id`, `tools_menu_active`, плюс динамические: `edit_mode_{car_id}`, `history_day_for_car_{car_id}`.

### 6.2 По сценариям

- **profile flow**: `awaiting_profile_name`, `awaiting_profile_avatar`, `awaiting_profile_rank_prefix`; критично хранить устойчиво только промежуточные шаги загрузки медиа/rename (DB optional, memory допустимо).  
- **admin flow**: `awaiting_admin_*`, `admin_user_back`; часть флагов чувствительна к рестарту процесса -> лучше durable storage (таблица `dialog_state` или Redis).  
- **combo flow**: `combo_builder`, `awaiting_combo_name`, `awaiting_combo_rename`; минимум `combo_builder` стоит делать durable (иначе потеря конструктора при рестарте).  
- **calendar flow**: `calendar_month`, `calendar_setup_days`, `calendar_edit_mode`; можно memory, но при долгих сценариях лучше persisted TTL state.  
- **history flow**: `history_decades_page`, `history_day_for_car_{car_id}`; можно memory.  
- **service search flow**: `awaiting_service_search`, `search_chat_id`, `search_message_id`; стоит держать TTL memory + fallback graceful cancel.  
- **avatar/media upload flow**: `awaiting_profile_avatar`, `awaiting_admin_faq_video`, `awaiting_admin_section_photo`; желательно durable-флаг на 5-15 минут.  
- **quick input/menu flow**: `awaiting_car_number`, `awaiting_distance`, `tools_menu_active`, `price_mode`; `price_mode` уже partly синхронизируется с DB, остальные можно memory.  

---

## 7) Анализ БД и идентификаторов

### 7.1 Где Telegram identity встроен в схему

- `users.telegram_id BIGINT UNIQUE NOT NULL`  
- `banned_users.telegram_id BIGINT UNIQUE NOT NULL`  
- `user_settings.goal_chat_id`, `user_settings.goal_message_id` (связка pinned message для Telegram chat/message).  
- `user_settings.telegram_avatar_path` и `avatar_source='telegram'` (семантика происхождения аватарки).  

### 7.2 Функции `database.py`, завязанные на `telegram_id`

- `get_user(telegram_id)`  
- `register_user(telegram_id, name)`  
- `is_telegram_banned(telegram_id)`  
- `unban_telegram_user(telegram_id)`  
- `ban_and_delete_user(...)` (переносит в `banned_users.telegram_id`)  
- ряд выборок leaderboard/admin возвращают `u.telegram_id` (UI-слой показывает Telegram ID).  

### 7.3 Минимально-разрушительная схема миграции identity

1. Добавить к `users` новые поля: `platform` (TEXT), `platform_user_id` (TEXT/BIGINT), оставить `telegram_id` временно.  
2. Добавить уникальный индекс `(platform, platform_user_id)`.  
3. Перевести lookup-функции на `get_user_by_platform(platform, platform_user_id)`; старые обёртки оставить временно.  
4. Аналогично для `banned_users` (`platform`, `platform_user_id`, legacy `telegram_id`).  
5. Для `goal_chat_id`/`goal_message_id` переименовать семантически в нейтральные `goal_recipient_id`/`goal_message_id` (или добавить новые и мигрировать чтение/запись постепенно).  
6. Для `telegram_avatar_path` заменить на `remote_avatar_path` (или добавить `max_avatar_path`) без удаления legacy-поля на первом шаге.  

> На этом этапе миграции SQL-скрипты не пишем; фиксируем перечень изменений.

---

## 8) Media/file flow (текущий Telegram vs MAX)

### 8.1 Где проект принимает медиа

- Профильный аватар: `_consume_profile_avatar_upload` (`message.photo` / `message.document` -> `get_file` -> локальный файл).  
- Админ-фото секций: `awaiting_admin_section_photo` (сохраняется `photo.file_id`).  
- FAQ-видео: `awaiting_admin_faq_video` (сохраняется `video.file_id` + source chat/message для copy).  

### 8.2 Где проект отправляет медиа/файлы

- Dashboard/leaderboard Pillow bytes: `reply_photo`/`send_photo` (`BytesIO`).  
- Документы: backup/pdf/xlsx через `reply_document`.  
- FAQ видео: `copy_message` / `send_video` по `file_id`.  
- Секционные фото/подписка: `photo=file_id` (reuse Telegram media id).

### 8.3 Telegram media assumptions, требующие переписывания

- Критичная зависимость на `file_id` как долгоживущий идентификатор вложения.  
- Дозагрузка user avatar через Telegram profile photos API.  
- Copy video между чатами через Telegram-specific `copy_message`.

### 8.4 Перенос на MAX upload flow

- Всё исходящее медиа: `upload_adapter.upload(bytes|file)` -> `token` -> `POST /messages` attachments.  
- Всё входящее медиа: читать attachments MAX в `message_created`, скачивать по `url`/media-method (требуется уточнение точной схемы).  
- Pillow-рендеры переносятся напрямую (побайтовая загрузка в upload flow).  
- UX-изменение вероятно для FAQ media reuse (вместо Telegram `file_id` хранить MAX media token/id и lifecycle policy).  

---

## 9) Анализ `api.py`

### 9.1 Что Telegram-specific

- `TaskPayload.chat_id` используется как внешний user key в `DatabaseManager.get_user(payload.chat_id)`.  
- `maybe_notify_telegram(...)` напрямую вызывает `https://api.telegram.org/bot{BOT_TOKEN}/sendMessage`.  
- ENV-флаг `NOTIFY_TELEGRAM` жёстко задаёт канал доставки.

### 9.2 Что менять для MAX

- Ввести `notify_max(...)` через `POST /messages` на `platform-api.max.ru` + `Authorization` header.  
- Заменить входной идентификатор: `chat_id` -> `platform_user_id` (или `user_id`), при необходимости оставить backward-compatible алиас в DTO (`chat_id` как deprecated).  
- `DatabaseManager.get_user(...)` перевести на platform-aware lookup.  
- Сохранить текущую бизнес-логику dedupe/shift/service без изменений.

### 9.3 Совместимость параметров API

- Рекомендуемый переходный контракт `/api/task`: принимать `user_id` и опционально legacy `chat_id`; валидировать «хотя бы одно поле».  
- В response причины ошибок оставить без изменений (`user_not_registered`, `no_active_shift`, etc.), чтобы не ломать клиентов.

---

## 10) Unknown / риски / пробелы

### 10.1 Подтверждено точно

- Домeн `platform-api.max.ru`, header auth `Authorization`.  
- Webhook (`POST /subscriptions`) + secret header `X-Max-Bot-Api-Secret`.  
- Long polling `GET /updates` (`types`, `marker`, `timeout`, `limit`).  
- Update types минимум `message_created` и `message_callback`.  
- Inline keyboard attachment + типы кнопок.  
- Callback answer `POST /answers?callback_id=...`.  
- Sending `POST /messages`, upload `POST /uploads`.  
- 30 rps, коды ошибок включая 429.

### 10.2 Unknown (обязательно проверить до coding)

1. Полная схема callback payload объекта в `message_callback` (где именно лежит payload кнопки).  
2. Точные параметры `PUT /messages` и idempotency/ограничения редактирования.  
3. Ограничения upload: максимальные размеры, TTL upload token, допустимые MIME, повторное использование token.  
4. Полная схема скачивания входящих attachment (URL auth? time-limited?).  
5. Есть ли нативный аналог reply keyboard в MAX; если нет — окончательная UX-замена.  
6. Поведение retry при webhook timeout >30s и backoff модель.  
7. Лимиты длины callback payload и ограничения по кнопкам конкретных типов в реальном API (помимо общих значений).  
8. Возможность pin/unpin/edit/delete в приватных диалогах и группах с ботом (rights model).  

### 10.3 Риски

- Потеря сценариев, завязанных на Telegram `file_id` reuse.  
- Нестабильность FSM при process restart без durable state.  
- Ошибки маппинга identity при смешанном периоде (`telegram_id` vs `max user_id`).  
- Перегрузка лимита 30 rps при массовых рассылках (нужен rate limiter + retry queue).

---

## 11) Пошаговый план миграции (без переписывания «с нуля»)

1. **Зафиксировать протокол MAX в проекте**: отдельный `docs/max_contract.md` с JSON-примерами `message_created`, `message_callback`, `POST /messages`, `POST /answers`, `POST /uploads` (только подтверждённые поля + TODO unknown).  
2. **Собрать Telegram adapter inventory**: выделить в `bot.py` все точки I/O Telegram API (send/edit/delete/callback/media) и обернуть в интерфейсный слой (`messaging gateway`) без изменения бизнес-логики.  
3. **Перевести входной event loop**: заменить PTB `Application`/handlers на MAX webhook/long-poll transport dispatcher, который вызывает существующие бизнес-функции через normalized event DTO.  
4. **Перенести callback flow**: сохранить exact/prefix payload grammar 1:1, поменять только транспорт извлечения payload + ACK через `POST /answers`.  
5. **Перенести клавиатуры**: генераторы `InlineKeyboardMarkup` -> генераторы MAX `inline_keyboard` attachment; reply keyboard сценарии перевести на inline-экраны.  
6. **Перенести state flow**: оставить memory для коротких ключей, добавить durable storage для критичных флагов (`admin/media/combo/profile-upload`) с TTL.  
7. **Перенести media flow**: реализовать upload adapter; заменить `file_id` хранилище на MAX media token/id схему; обновить FAQ/section/profile media pipelines.  
8. **Мигрировать identity в БД**: добавить platform-aware поля/индексы, обновить lookup API в `database.py`, затем заменить вызовы в `bot.py` и `api.py`; legacy `telegram_id` оставить на переходный период.  
9. **Обновить `api.py`**: DTO (`user_id`/legacy `chat_id`), отправка уведомлений через MAX sender, удалить прямую зависимость от Telegram endpoint.  
10. **Фоновые задачи**: заменить `job_queue` на scheduler вне PTB (cron/apscheduler/worker), добавить rate limiter (30 rps) + retry policy для 429/503.  
11. **Тесты после миграции**:  
   - unit: parser callback payload, state transitions, keyboard JSON builders;  
   - integration: webhook signature validation, callback answer, upload->send media chain;  
   - regression: ключевые сценарии (старт/смены/машины/услуги/история/календарь/профиль/FAQ/комбо/leaderboard/admin/очистка/экспорт/уведомления).  

---

## Примечание о двух `handle_message`

В `bot.py` объявлено **две функции** `handle_message`. Активной является **вторая** (нижняя в файле), т.к. в Python последнее определение с тем же именем перезаписывает предыдущее. Регистрация handler (`safe_handle_message -> handle_message`) использует уже второе определение. Это критично учесть до миграции.
