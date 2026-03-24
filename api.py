import logging
import os
import re
import asyncio

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator

from config import BOT_TOKEN, SERVICES
from database import DatabaseManager, get_connection, init_database
from max_api import MaxClient
from bot import process_max_update, ensure_startup_once, notify_subscription_events, notify_shift_close_prompts, scheduled_period_reports

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ServiceBot API", version="1.0.0")
max_client = MaxClient(BOT_TOKEN)
MAX_WEBHOOK_SECRET = os.getenv("MAX_WEBHOOK_SECRET", "")
_bg_tasks: list[asyncio.Task] = []

FAST_SERVICE_ALIASES = {
    1: ["проверка", "пров", "провер", "чек"],
    2: ["заправка", "запр", "топливо", "бенз"],
    3: ["омыв", "омывка", "омывайка", "зали", "зо", "заливка"],
    14: ["перепарковка", "перепарк", "парковка", "некорректная", "некк", "нек", "некорр"],
}


class TaskPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: int | None = None
    chat_id: int | None = None
    car_id: str
    task_type: str | int
    timestamp: int
    device_key: str | None = None

    @field_validator("car_id")
    @classmethod
    def validate_car_id(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("car_id_required")
        return normalized

    @property
    def actor_id(self) -> int:
        return int(self.user_id or self.chat_id or 0)


def plain_service_name(name: str) -> str:
    return re.sub(r"^[^0-9A-Za-zА-Яа-я]+\s*", "", name).strip()


def resolve_service_id(task_type: str | int) -> int | None:
    if isinstance(task_type, int):
        return task_type if task_type in SERVICES else None

    normalized = str(task_type).strip().lower()
    if not normalized:
        return None

    if normalized.isdigit():
        numeric = int(normalized)
        return numeric if numeric in SERVICES else None

    for service_id, aliases in FAST_SERVICE_ALIASES.items():
        if normalized in aliases:
            return service_id

    for service_id, service in SERVICES.items():
        clean_name = plain_service_name(service.get("name", "")).lower()
        if normalized in clean_name or clean_name in normalized:
            return service_id

    return None


def is_duplicate_recent(car_id: int, service_id: int, ttl_hours: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT 1
        FROM car_services
        WHERE car_id = ?
          AND service_id = ?
          AND datetime(created_at) >= datetime('now', ?)
        LIMIT 1""",
        (car_id, service_id, f"-{ttl_hours} hours"),
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def maybe_notify_max(user_id: int, car_number: str, service_name: str, price: int) -> None:
    if os.getenv("NOTIFY_MAX", "1") != "1":
        return

    text = f"✅ Добавлена услуга: {service_name}\n🚗 {car_number}\n💰 {price}₽"
    try:
        max_client.send_message(user_id=user_id, text=text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MAX notify failed: %s", exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    reason = "invalid_payload"
    if exc.errors():
        reason = str(exc.errors()[0].get("msg", reason))
    return JSONResponse(status_code=422, content={"status": "error", "reason": reason})


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error: %s", exc)
    return JSONResponse(status_code=500, content={"status": "error", "reason": "internal_error"})


@app.on_event("startup")
async def on_startup() -> None:
    init_database()
    await ensure_startup_once()
    _bg_tasks.append(asyncio.create_task(_run_hourly_jobs()))
    _bg_tasks.append(asyncio.create_task(_run_daily_report_jobs()))


@app.on_event("shutdown")
async def on_shutdown() -> None:
    for task in _bg_tasks:
        task.cancel()
    _bg_tasks.clear()


async def _run_hourly_jobs() -> None:
    while True:
        try:
            await notify_subscription_events(_APP_PROXY)
        except Exception as exc:  # noqa: BLE001
            logger.warning("hourly subscription job failed: %s", exc)
        try:
            await notify_shift_close_prompts(_APP_PROXY)
        except Exception as exc:  # noqa: BLE001
            logger.warning("hourly shift prompt job failed: %s", exc)
        await asyncio.sleep(3600)


class _AsyncBotProxy:
    async def send_message(self, *, chat_id: int, text: str, reply_markup=None):
        attachments = []
        if reply_markup is not None:
            from max_runtime import _serialize_markup  # type: ignore
            attachments = _serialize_markup(reply_markup)
        max_client.send_message(chat_id=chat_id, text=text, attachments=attachments)


_APP_PROXY = type("_AppProxy", (), {"bot": _AsyncBotProxy()})()


async def _run_daily_report_jobs() -> None:
    while True:
        try:
            await scheduled_period_reports(_APP_PROXY)
        except Exception as exc:  # noqa: BLE001
            logger.warning("daily report job failed: %s", exc)
        await asyncio.sleep(3600)


@app.post("/api/task")
async def create_task(payload: TaskPayload) -> JSONResponse:
    required_device_key = os.getenv("DEVICE_KEY")
    if required_device_key and payload.device_key != required_device_key:
        return JSONResponse(status_code=401, content={"status": "error", "reason": "unauthorized"})

    actor_id = payload.actor_id
    if actor_id <= 0:
        return JSONResponse(status_code=422, content={"status": "error", "reason": "user_id_required"})

    user = DatabaseManager.get_user(actor_id)
    if not user:
        return JSONResponse(status_code=404, content={"status": "error", "reason": "user_not_registered"})

    shift = DatabaseManager.get_active_shift(user["id"])
    if not shift:
        if os.getenv("AUTO_START_SHIFT", "0") == "1":
            shift_id = DatabaseManager.start_shift(user["id"])
            shift = DatabaseManager.get_shift(shift_id)
        else:
            return JSONResponse(status_code=409, content={"status": "error", "reason": "no_active_shift"})

    car_number = payload.car_id
    shift_cars = DatabaseManager.get_shift_cars(shift["id"])
    car = next((item for item in shift_cars if str(item.get("car_number", "")).strip().upper() == car_number), None)
    if car:
        car_db_id = int(car["id"])
    else:
        car_db_id = DatabaseManager.add_car(shift["id"], car_number)

    service_id = resolve_service_id(payload.task_type)
    if service_id is None:
        return JSONResponse(status_code=422, content={"status": "error", "reason": "unknown_task_type"})

    ttl_hours = max(1, int(os.getenv("DEDUPE_TTL_HOURS", "6")))
    if is_duplicate_recent(car_db_id, service_id, ttl_hours):
        return JSONResponse(status_code=200, content={"status": "ok", "dedup": True})

    service = SERVICES[service_id]
    service_name = plain_service_name(service.get("name", ""))
    price_mode = DatabaseManager.get_price_mode(user["id"])
    price_key = "night_price" if price_mode == "night" else "day_price"
    price = int(service.get(price_key, 0) or 0)

    DatabaseManager.add_service_to_car(car_db_id, service_id, service_name, price)
    maybe_notify_max(actor_id, car_number, service_name, price)

    return JSONResponse(status_code=200, content={"status": "ok"})


@app.post("/max/webhook")
async def max_webhook(update: dict, x_max_bot_api_secret: str | None = Header(default=None)) -> JSONResponse:
    if MAX_WEBHOOK_SECRET and x_max_bot_api_secret != MAX_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid_secret")
    await process_max_update(update)
    return JSONResponse(status_code=200, content={"status": "ok"})
