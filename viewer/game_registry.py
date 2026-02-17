"""Persistent game registry stored in JSON."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import InvalidRequestError, NotFoundError

REGISTRY_VERSION = 1

_UNSET = object()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class GameEntry:
    id: str
    name: str
    cover_image: str
    exe_path: str
    data_path: str
    engine: str
    added_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameEntry":
        engine = str(data.get("engine", "mv") or "mv").strip().lower()
        if engine not in ("mv", "vx", "vxace"):
            engine = "mv"
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")).strip(),
            cover_image=str(data.get("cover_image", "") or "").strip(),
            exe_path=str(data.get("exe_path", "")).strip(),
            data_path=str(data.get("data_path", "")).strip(),
            engine=engine,
            added_at=str(data.get("added_at", "") or ""),
            updated_at=str(data.get("updated_at", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "cover_image": self.cover_image,
            "exe_path": self.exe_path,
            "data_path": self.data_path,
            "engine": self.engine,
            "added_at": self.added_at,
            "updated_at": self.updated_at,
        }

    def is_available(self) -> bool:
        if self.engine == "mv":
            return (Path(self.data_path) / "MapInfos.json").exists()

        data_dir = Path(self.data_path)
        if (data_dir / "MapInfos.rvdata2").exists() or (data_dir / "MapInfos.rvdata").exists():
            return True

        root = Path(self.exe_path).parent
        if self.engine == "vxace" and (root / "Game.rgss3a").exists():
            return True
        if self.engine == "vx" and ((root / "Game.rgss2a").exists() or (root / "Game.rgssad").exists()):
            return True
        return False


class GameRegistry:
    """Read/write helper around games_registry.json."""

    def __init__(self, registry_path: str | Path):
        self.path = Path(registry_path).resolve()
        self.last_warning: str = ""
        self._data = self._load_or_init()

    def _empty_data(self) -> dict[str, Any]:
        return {
            "version": REGISTRY_VERSION,
            "active_game_id": "",
            "games": [],
        }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self.path)

    def _normalize_data(self, raw: dict[str, Any]) -> dict[str, Any]:
        out = self._empty_data()
        if isinstance(raw.get("version"), int):
            out["version"] = raw["version"]
        active_id = raw.get("active_game_id", "")
        out["active_game_id"] = str(active_id) if active_id is not None else ""

        games: list[dict[str, Any]] = []
        if isinstance(raw.get("games"), list):
            for item in raw["games"]:
                if not isinstance(item, dict):
                    continue
                entry = GameEntry.from_dict(item)
                if not entry.id or not entry.exe_path or not entry.data_path:
                    continue
                if not entry.name:
                    entry.name = Path(entry.exe_path).stem or "未命名游戏"
                if not entry.added_at:
                    entry.added_at = _now_iso()
                if not entry.updated_at:
                    entry.updated_at = entry.added_at
                games.append(entry.to_dict())
        out["games"] = games

        if out["active_game_id"] and not any(g["id"] == out["active_game_id"] for g in games):
            out["active_game_id"] = ""
        return out

    def _load_or_init(self) -> dict[str, Any]:
        if not self.path.exists():
            data = self._empty_data()
            self._data = data
            self._save()
            return data

        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise ValueError("registry root is not object")
            data = self._normalize_data(raw)
            self._data = data
            self._save()
            return data
        except Exception as exc:  # noqa: BLE001
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = self.path.with_name(f"games_registry.broken.{ts}.json")
            try:
                shutil.copyfile(self.path, backup)
                self.last_warning = (
                    f"游戏库文件损坏，已备份为 {backup.name} 并重建。错误: {exc}"
                )
            except Exception:  # noqa: BLE001
                self.last_warning = f"游戏库文件损坏且备份失败，已重建。错误: {exc}"
            data = self._empty_data()
            self._data = data
            self._save()
            return data

    def list_games(self) -> list[GameEntry]:
        return [GameEntry.from_dict(x) for x in self._data.get("games", [])]

    def get_game(self, game_id: str) -> GameEntry:
        for entry in self.list_games():
            if entry.id == game_id:
                return entry
        raise NotFoundError(f"游戏不存在: {game_id}")

    def get_active_game_id(self) -> str:
        return str(self._data.get("active_game_id", "") or "")

    def get_active_game(self) -> GameEntry | None:
        game_id = self.get_active_game_id()
        if not game_id:
            return None
        try:
            return self.get_game(game_id)
        except NotFoundError:
            return None

    def set_active_game(self, game_id: str) -> GameEntry:
        game = self.get_game(game_id)
        self._data["active_game_id"] = game.id
        self._save()
        return game

    def clear_active_game(self) -> None:
        self._data["active_game_id"] = ""
        self._save()

    def upsert_game(
        self,
        exe_path: str | Path,
        data_path: str | Path,
        name: str | None = None,
        engine: str = "mv",
    ) -> GameEntry:
        exe = str(Path(exe_path).expanduser().resolve())
        data = str(Path(data_path).expanduser().resolve())
        normalized_engine = (engine or "mv").strip().lower()
        if normalized_engine not in ("mv", "vx", "vxace"):
            normalized_engine = "mv"
        now = _now_iso()

        for i, raw in enumerate(self._data["games"]):
            if raw["exe_path"] == exe or raw["data_path"] == data:
                existing = GameEntry.from_dict(raw)
                existing.exe_path = exe
                existing.data_path = data
                existing.engine = normalized_engine
                existing.updated_at = now
                if name and name.strip():
                    existing.name = name.strip()
                self._data["games"][i] = existing.to_dict()
                if not self._data.get("active_game_id"):
                    self._data["active_game_id"] = existing.id
                self._save()
                return existing

        entry = GameEntry(
            id=str(uuid.uuid4()),
            name=(name.strip() if name and name.strip() else Path(exe).stem or "未命名游戏"),
            cover_image="",
            exe_path=exe,
            data_path=data,
            engine=normalized_engine,
            added_at=now,
            updated_at=now,
        )
        self._data["games"].append(entry.to_dict())
        if not self._data.get("active_game_id"):
            self._data["active_game_id"] = entry.id
        self._save()
        return entry

    def update_game(self, game_id: str, *, name: str | None = None, cover_image: Any = _UNSET) -> GameEntry:
        games = self._data.get("games", [])
        for i, raw in enumerate(games):
            if raw.get("id") != game_id:
                continue
            entry = GameEntry.from_dict(raw)
            if name is not None:
                name_val = name.strip()
                if not name_val:
                    raise InvalidRequestError("游戏名称不能为空")
                entry.name = name_val
            if cover_image is not _UNSET:
                entry.cover_image = str(cover_image or "").strip()
            entry.updated_at = _now_iso()
            games[i] = entry.to_dict()
            self._save()
            return entry
        raise NotFoundError(f"游戏不存在: {game_id}")

    def delete_game(self, game_id: str) -> None:
        games = self._data.get("games", [])
        new_games = [g for g in games if g.get("id") != game_id]
        if len(new_games) == len(games):
            raise NotFoundError(f"游戏不存在: {game_id}")
        self._data["games"] = new_games
        if self._data.get("active_game_id") == game_id:
            self._data["active_game_id"] = new_games[0]["id"] if new_games else ""
        self._save()

    def as_payload(self) -> dict[str, Any]:
        active_id = self.get_active_game_id()
        games = []
        for game in self.list_games():
            games.append(
                {
                    **game.to_dict(),
                    "is_active": game.id == active_id,
                    "is_available": game.is_available(),
                }
            )
        return {
            "version": self._data.get("version", REGISTRY_VERSION),
            "active_game_id": active_id,
            "games": games,
            "warning": self.last_warning,
        }
