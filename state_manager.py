from __future__ import annotations

<<<<<<< codex/create-technical-specification-for-max-migration-meyrbj
from threading import RLock
from typing import Any
import json
import logging

from database import DatabaseManager

logger = logging.getLogger(__name__)

PERSISTED_PREFIXES = (
    "awaiting_admin_",
    "awaiting_profile_",
    "awaiting_combo_",
    "awaiting_service_search",
    "awaiting_distance",
    "awaiting_car_number",
)


class PersistentUserState(dict):
    def __init__(self, user_id: int, initial: dict[str, Any] | None = None):
        super().__init__(initial or {})
        self._user_id = int(user_id)

    def _sync(self) -> None:
        persistent = {k: v for k, v in self.items() if _is_persisted_key(k)}
        key = f"runtime_state:{self._user_id}"
        try:
            DatabaseManager.set_app_content(key, json.dumps(persistent, ensure_ascii=False))
        except Exception:
            logger.exception("state sync failed user_id=%s", self._user_id)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._sync()

    def pop(self, key, default=None):
        val = super().pop(key, default)
        self._sync()
        return val

    def clear(self):
        super().clear()
        self._sync()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._sync()


def _is_persisted_key(key: str) -> bool:
    return any(key == p or key.startswith(p) for p in PERSISTED_PREFIXES)
=======
from collections import defaultdict
from threading import RLock
from typing import Any
>>>>>>> main


class StateManager:
    def __init__(self):
        self._lock = RLock()
<<<<<<< codex/create-technical-specification-for-max-migration-meyrbj
        self._store: dict[int, PersistentUserState] = {}

    def get_user_state(self, user_id: int) -> PersistentUserState:
        with self._lock:
            uid = int(user_id)
            existing = self._store.get(uid)
            if existing:
                return existing
            raw = DatabaseManager.get_app_content(f"runtime_state:{uid}", "")
            data: dict[str, Any] = {}
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        data = parsed
                except Exception:
                    logger.warning("invalid persisted runtime_state user_id=%s", uid)
            state = PersistentUserState(uid, data)
            self._store[uid] = state
            return state

    def clear_user_state(self, user_id: int) -> None:
        with self._lock:
            uid = int(user_id)
            self._store.pop(uid, None)
            DatabaseManager.set_app_content(f"runtime_state:{uid}", "")
=======
        self._store: dict[int, dict[str, Any]] = defaultdict(dict)

    def get_user_state(self, user_id: int) -> dict[str, Any]:
        with self._lock:
            return self._store[int(user_id)]

    def clear_user_state(self, user_id: int) -> None:
        with self._lock:
            self._store.pop(int(user_id), None)
>>>>>>> main


state_manager = StateManager()
