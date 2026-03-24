from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Any


class StateManager:
    def __init__(self):
        self._lock = RLock()
        self._store: dict[int, dict[str, Any]] = defaultdict(dict)

    def get_user_state(self, user_id: int) -> dict[str, Any]:
        with self._lock:
            return self._store[int(user_id)]

    def clear_user_state(self, user_id: int) -> None:
        with self._lock:
            self._store.pop(int(user_id), None)


state_manager = StateManager()
