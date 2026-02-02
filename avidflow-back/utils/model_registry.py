from __future__ import annotations
from typing import Any, Dict, Optional
import threading
import uuid

class ModelAdapterProtocol:
    # Minimal interface the agent expects
    def invoke(self, messages: list[dict], tools: Optional[list[dict]] = None) -> dict:  # returns {"assistant_message": {...}, "tool_calls": [...]}
        raise NotImplementedError

class _Registry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: Dict[str, Any] = {}

    def register(self, adapter: Any) -> str:
        rid = uuid.uuid4().hex
        with self._lock:
            self._store[rid] = adapter
        return rid

    def get(self, rid: str) -> Optional[Any]:
        with self._lock:
            return self._store.get(rid)

    def unregister(self, rid: str) -> None:
        with self._lock:
            self._store.pop(rid, None)

ModelRegistry = _Registry()