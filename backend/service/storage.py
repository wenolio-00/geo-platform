from __future__ import annotations

import contextlib
import logging
import json
import threading
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - POSIX file locking is available in deployed macOS/Linux envs.
    fcntl = None  # type: ignore[assignment]


BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = BASE_DIR / "storage"
logger = logging.getLogger(__name__)


class JsonStore:
    def __init__(self, filename: str):
        self.path = STORAGE_DIR / filename
        self.lock_path = STORAGE_DIR / f"{filename}.lock"
        self._lock = threading.RLock()
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.write({})

    def read(self) -> dict[str, Any]:
        with self._lock:
            return self._read_unlocked()

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError:
            logger.exception(
                "json_store_decode_failed",
                extra={"store_path": str(self.path), "stage": "read"},
            )
            data = {}
        except FileNotFoundError:
            data = {}
        return data if isinstance(data, dict) else {}

    def write(self, data: dict[str, Any]) -> None:
        with self._lock, self._exclusive_file_lock():
            self._write_unlocked(data)

    def _write_unlocked(self, data: dict[str, Any]) -> None:
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(self.path)

    def get(self, key: str) -> dict[str, Any] | None:
        value = self.read().get(key)
        return value if isinstance(value, dict) else None

    def upsert(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._exclusive_file_lock():
            data = self._read_unlocked()
            data[key] = value
            self._write_unlocked(data)
        return value

    @contextlib.contextmanager
    def _exclusive_file_lock(self):
        self.lock_path.touch(exist_ok=True)
        with self.lock_path.open("r+", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


brand_configs_store = JsonStore("brand_configs.json")
runs_store = JsonStore("diagnostic_runs.json")
querysets_store = JsonStore("querysets.json")
inspection_results_store = JsonStore("inspection_results.json")
brand_dashboard_snapshots_store = JsonStore("brand_dashboard_snapshots.json")
content_versions_store = JsonStore("content_versions.json")
content_feedback_store = JsonStore("content_feedback.json")
effect_attribution_store = JsonStore("effect_attribution.json")
iteration_priority_board_store = JsonStore("iteration_priority_board.json")
