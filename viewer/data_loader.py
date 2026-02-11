"""Data loading scoped to one game (MV JSON or VX/VX Ace marshal)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._vendor.rubymarshal.reader import loads as marshal_loads
from .errors import GameDataInvalidError
from .rgss_archive import RgssArchive
from .vx_adapter import VXDataAdapter

_SENTINEL = object()


class DataLoader:
    """Loads game data from MV JSON or VX/VX Ace rvdata files."""

    def __init__(self, data_dir: str | Path, engine: str = "mv", archive_path: str | Path | None = None):
        self.data_dir = Path(data_dir).resolve()
        self.engine = (engine or "mv").strip().lower()
        if self.engine not in ("mv", "vx", "vxace"):
            self.engine = "mv"
        self._cache: dict[str, Any] = {}
        self.archive: RgssArchive | None = None

        if self.engine in ("vx", "vxace") and archive_path:
            archive = Path(archive_path).expanduser().resolve()
            if archive.exists():
                self.archive = RgssArchive(archive)
            else:
                raise GameDataInvalidError(f"归档文件不存在: {archive}")

    def file_path(self, filename: str) -> Path:
        return self.data_dir / filename

    def exists(self, filename: str) -> bool:
        if self.engine == "mv":
            return self.file_path(filename).exists()
        return self._locate_vx_source(filename) is not None

    def load_json(self, filename: str) -> Any:
        cache_key = filename.lower()
        if cache_key in self._cache:
            value = self._cache[cache_key]
            return None if value is _SENTINEL else value

        if self.engine == "mv":
            value = self._load_mv_json(filename)
        else:
            value = self._load_vx_data(filename)

        self._cache[cache_key] = _SENTINEL if value is None else value
        return value

    def _load_mv_json(self, filename: str) -> Any:
        filepath = self.file_path(filename)
        try:
            with filepath.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _load_vx_data(self, filename: str) -> Any:
        source = self._locate_vx_source(filename)
        if source is None:
            return None

        source_type, source_value = source
        try:
            if source_type == "disk":
                raw_bytes = Path(source_value).read_bytes()
            else:
                if not self.archive:
                    return None
                raw_bytes = self.archive.read_entry(str(source_value))
            raw_obj = marshal_loads(raw_bytes)
            return VXDataAdapter.adapt(filename, raw_obj)
        except Exception:  # noqa: BLE001
            return None

    def _vx_candidates(self, filename: str) -> list[str]:
        name = Path(filename).name
        lower = name.lower()
        if lower.endswith(".json"):
            base = name[:-5]
            return [f"{base}.rvdata2", f"{base}.rvdata"]
        if lower.endswith(".rvdata2") or lower.endswith(".rvdata"):
            return [name]
        return [f"{name}.rvdata2", f"{name}.rvdata"]

    def _locate_vx_source(self, filename: str) -> tuple[str, Any] | None:
        for candidate in self._vx_candidates(filename):
            disk = self.data_dir / candidate
            if disk.exists() and disk.is_file():
                return ("disk", disk)

        if not self.archive:
            return None

        for candidate in self._vx_candidates(filename):
            for entry_name in (
                f"Data\\{candidate}",
                f"data\\{candidate}",
                candidate,
            ):
                if self.archive.has_entry(entry_name):
                    return ("archive", entry_name)
        return None
