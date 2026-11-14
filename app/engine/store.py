"""Thread-safe in-memory LRU storage of completed analyses."""

import hashlib
import json
from collections import OrderedDict
from threading import RLock
from typing import Any

from app.schemas import AnalysisRequest
from app.settings import ANALYSIS_CACHE_SIZE


class AnalysisStore:
    def __init__(self, capacity: int = ANALYSIS_CACHE_SIZE) -> None:
        self.capacity = capacity
        self._items: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._keys: dict[str, str] = {}
        self._next_id = 1
        self.lock = RLock()

    @staticmethod
    def request_key(request: AnalysisRequest) -> str:
        payload = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def find(self, request: AnalysisRequest) -> dict[str, Any] | None:
        with self.lock:
            analysis_id = self._keys.get(self.request_key(request))
            return self.get(analysis_id) if analysis_id else None

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        with self.lock:
            result = self._items.get(analysis_id)
            if result is not None:
                self._items.move_to_end(analysis_id)
            return result

    def put(self, request: AnalysisRequest, result: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            existing = self.find(request)
            if existing is not None:
                return existing
            analysis_id = f"analysis_{self._next_id:03d}"
            self._next_id += 1
            result["analysisId"] = analysis_id
            result["_requestKey"] = self.request_key(request)
            self._items[analysis_id] = result
            self._keys[result["_requestKey"]] = analysis_id
            if len(self._items) > self.capacity:
                _, oldest = self._items.popitem(last=False)
                self._keys.pop(oldest["_requestKey"], None)
            return result
