from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = BASE_DIR / "storage"


class JsonStore:
    def __init__(self, filename: str):
        self.path = STORAGE_DIR / filename
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.write({})

    def read(self) -> dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {}
        return data if isinstance(data, dict) else {}

    def write(self, data: dict[str, Any]) -> None:
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(self.path)

    def get(self, key: str) -> dict[str, Any] | None:
        value = self.read().get(key)
        return value if isinstance(value, dict) else None

    def upsert(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        data = self.read()
        data[key] = value
        self.write(data)
        return value


brand_configs_store = JsonStore("brand_configs.json")
runs_store = JsonStore("diagnostic_runs.json")
querysets_store = JsonStore("querysets.json")
inspection_results_store = JsonStore("inspection_results.json")
brand_dashboard_snapshots_store = JsonStore("brand_dashboard_snapshots.json")
content_versions_store = JsonStore("content_versions.json")
content_feedback_store = JsonStore("content_feedback.json")
effect_attribution_store = JsonStore("effect_attribution.json")
