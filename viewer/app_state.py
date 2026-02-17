"""Application state and active-game runtime context."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_loader import DataLoader
from .database import DatabaseManager
from .errors import GameDataInvalidError, NoActiveGameError
from .exporter import ExportService
from .game_discovery import discover_game_from_exe
from .game_registry import GameEntry, GameRegistry
from .interpreter import EventInterpreter
from .java_mv_decrypter import find_java_decrypter_jar, run_java_decrypt
from .mv_mz_resource_unpack import PrepareResult, prepare_resources
from .paths import PROJECT_ROOT


@dataclass
class ActiveContext:
    game: GameEntry
    loader: DataLoader
    db: DatabaseManager
    interpreter: EventInterpreter
    exporter: ExportService


class AppState:
    """Holds current selected game runtime components."""

    def __init__(self, registry: GameRegistry):
        self.registry = registry
        self._context: ActiveContext | None = None
        self.last_prepare_result: dict[str, Any] | None = None
        self._sync_active_context()

    @staticmethod
    def _is_generic_name(name: str) -> bool:
        text = (name or "").strip().lower()
        return text in {"", "game", "未命名游戏"}

    @staticmethod
    def _read_game_ini_title(game_root: Path) -> str | None:
        ini_path = game_root / "Game.ini"
        if not ini_path.exists() or not ini_path.is_file():
            return None

        raw = None
        for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis", "gbk", "latin1"):
            try:
                raw = ini_path.read_text(encoding=enc)
                break
            except Exception:  # noqa: BLE001
                continue
        if raw is None:
            return None

        parser = configparser.ConfigParser()
        try:
            parser.read_string(raw)
        except Exception:  # noqa: BLE001
            return None

        title = parser.get("Game", "Title", fallback="").strip()
        return title or None

    @staticmethod
    def _find_first_image(directory: Path) -> Path | None:
        if not directory.exists() or not directory.is_dir():
            return None
        files = sorted(
            [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
        )
        if not files:
            return None
        return files[0]

    def _infer_name_from_data(
        self,
        game_root: Path,
        data_path: Path,
        engine: str,
        archive_path: Path | None,
        exe_path: Path,
    ) -> str:
        ini_title = self._read_game_ini_title(game_root)
        if ini_title and not self._is_generic_name(ini_title):
            return ini_title

        try:
            loader = DataLoader(data_path, engine=engine, archive_path=archive_path)
            system = loader.load_json("System.json")
            if isinstance(system, dict):
                title = str(system.get("gameTitle", "") or "").strip()
                if title and not self._is_generic_name(title):
                    return title
        except Exception:  # noqa: BLE001
            pass

        stem = exe_path.stem.strip()
        if stem and not self._is_generic_name(stem):
            return stem
        parent_name = game_root.name.strip()
        if parent_name:
            return parent_name
        return "未命名游戏"

    def _select_cover_image(
        self,
        game_root: Path,
        data_path: Path,
        engine: str,
        archive_path: Path | None,
        prepare_output_dir: str | None,
    ) -> str:
        title1 = ""
        title2 = ""
        try:
            loader = DataLoader(data_path, engine=engine, archive_path=archive_path)
            system = loader.load_json("System.json")
            if isinstance(system, dict):
                title1 = str(system.get("title1Name", "") or "").strip()
                title2 = str(system.get("title2Name", "") or "").strip()
        except Exception:  # noqa: BLE001
            pass

        roots: list[Path] = []
        if prepare_output_dir:
            out = Path(prepare_output_dir)
            if out.exists():
                roots.extend([out, out / "www"])
        roots.extend([game_root / "www", game_root])

        candidates: list[Path] = []
        for base in roots:
            if title1:
                for ext in (".png", ".jpg", ".jpeg", ".webp"):
                    candidates.append(base / "img" / "titles1" / f"{title1}{ext}")
            if title2:
                for ext in (".png", ".jpg", ".jpeg", ".webp"):
                    candidates.append(base / "img" / "titles2" / f"{title2}{ext}")

        if engine in ("vx", "vxace"):
            for base in roots:
                candidates.extend(
                    [
                        base / "Graphics" / "System" / "Title.png",
                        base / "Graphics" / "System" / "Title.jpg",
                    ]
                )

        for path in candidates:
            if path.exists() and path.is_file():
                return str(path.resolve())

        search_dirs = [
            "img/titles1",
            "img/titles2",
            "img/pictures",
            "Graphics/Titles1",
            "Graphics/Titles2",
            "Graphics/System",
        ]
        for base in roots:
            for rel in search_dirs:
                found = self._find_first_image(base / rel)
                if found:
                    return str(found.resolve())

        return ""

    @staticmethod
    def _resolve_archive_path(game: GameEntry) -> Path | None:
        root = Path(game.exe_path).expanduser().resolve().parent
        if game.engine == "vxace":
            candidate = root / "Game.rgss3a"
            return candidate if candidate.exists() else None
        if game.engine == "vx":
            for name in ("Game.rgss2a", "Game.rgssad"):
                candidate = root / name
                if candidate.exists():
                    return candidate
        return None

    def _build_context(self, game: GameEntry) -> ActiveContext:
        archive_path = self._resolve_archive_path(game)
        loader = DataLoader(game.data_path, engine=game.engine, archive_path=archive_path)
        if not loader.exists("MapInfos.json"):
            raise GameDataInvalidError(f"游戏数据无效或缺失地图信息: {game.data_path}")
        db = DatabaseManager(loader)
        interpreter = EventInterpreter(db)
        exporter = ExportService(loader, db, interpreter)
        return ActiveContext(
            game=game,
            loader=loader,
            db=db,
            interpreter=interpreter,
            exporter=exporter,
        )

    def _sync_active_context(self) -> None:
        active = self.registry.get_active_game()
        if not active:
            self._context = None
            return
        try:
            self._context = self._build_context(active)
        except GameDataInvalidError:
            self._context = None

    def refresh(self) -> None:
        self._sync_active_context()

    @staticmethod
    def _java_prepare_runner(game_root: Path, output_dir: Path) -> tuple[bool, str]:
        jar_path = find_java_decrypter_jar(PROJECT_ROOT)
        return run_java_decrypt(game_root, output_dir, jar_path)

    def get_last_prepare_result(self) -> dict[str, Any] | None:
        if self.last_prepare_result is None:
            return None
        return dict(self.last_prepare_result)

    def register_exe(self, exe_path: str, name: str | None = None, make_active: bool = False) -> GameEntry:
        self.last_prepare_result = None
        discovery = discover_game_from_exe(exe_path)
        exe_resolved = Path(exe_path).expanduser().resolve()
        game_root = exe_resolved.parent
        data_resolved = discovery.data_dir.resolve()
        archive_path = discovery.archive_path.resolve() if discovery.archive_path else None

        existing = None
        for game in self.registry.list_games():
            if game.exe_path == str(exe_resolved) or game.data_path == str(data_resolved):
                existing = game
                break

        final_name = (name or "").strip()
        if not final_name:
            if existing and not self._is_generic_name(existing.name):
                final_name = existing.name
            else:
                final_name = self._infer_name_from_data(
                    game_root=game_root,
                    data_path=data_resolved,
                    engine=discovery.engine,
                    archive_path=archive_path,
                    exe_path=exe_resolved,
                )

        entry = self.registry.upsert_game(
            exe_path=exe_path,
            data_path=discovery.data_dir,
            name=final_name,
            engine=discovery.engine,
        )

        prepare_output_dir = ""

        if discovery.engine == "mv":
            cache_dir = game_root / "data_cache"
            try:
                prepare_result = prepare_resources(
                    game_root=game_root,
                    data_dir=Path(entry.data_path),
                    cache_dir=cache_dir,
                    java_runner=self._java_prepare_runner,
                )
            except Exception as exc:  # noqa: BLE001
                prepare_result = PrepareResult(
                    status="failed",
                    method="none",
                    message=f"资源解包流程异常: {exc}",
                    output_dir=str((cache_dir / "decrypted").resolve()),
                    processed_files=0,
                    failed_files=0,
                )
            self.last_prepare_result = prepare_result.to_dict()
            prepare_output_dir = prepare_result.output_dir

        if not (entry.cover_image or "").strip():
            cover_image = self._select_cover_image(
                game_root=game_root,
                data_path=data_resolved,
                engine=discovery.engine,
                archive_path=archive_path,
                prepare_output_dir=prepare_output_dir or None,
            )
            if cover_image:
                entry = self.registry.update_game(entry.id, cover_image=cover_image)

        if make_active:
            self.registry.set_active_game(entry.id)
        self._sync_active_context()
        return entry

    def select_game(self, game_id: str) -> ActiveContext:
        game = self.registry.get_game(game_id)
        context = self._build_context(game)
        self.registry.set_active_game(game_id)
        self._context = context
        return self._context

    def update_game(self, game_id: str, *, name: str | None = None, cover_image: Any = None, cover_provided: bool = False) -> GameEntry:
        if cover_provided:
            entry = self.registry.update_game(game_id, name=name, cover_image=cover_image)
        else:
            entry = self.registry.update_game(game_id, name=name)
        if self.registry.get_active_game_id() == entry.id:
            self._sync_active_context()
        return entry

    def delete_game(self, game_id: str) -> None:
        self.registry.delete_game(game_id)
        self._sync_active_context()

    def get_active_context(self) -> ActiveContext:
        active = self.registry.get_active_game()
        if not active:
            raise NoActiveGameError("当前未选择游戏，请先通过 game_tool.bat 或游戏库管理添加并选择游戏")
        if not self._context or self._context.game.id != active.id:
            self._context = self._build_context(active)
        return self._context
