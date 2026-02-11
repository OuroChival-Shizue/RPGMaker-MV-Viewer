"""Discover game engine and data location from an executable path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import GameDataInvalidError, InvalidRequestError


@dataclass(frozen=True)
class GameDiscoveryResult:
    engine: str
    data_dir: Path
    archive_path: Path | None = None


def _has_any(root: Path, pattern: str) -> bool:
    if not root.exists():
        return False
    try:
        return any(root.glob(pattern))
    except Exception:  # noqa: BLE001
        return False


def discover_game_from_exe(exe_path: str | Path) -> GameDiscoveryResult:
    exe = Path(exe_path).expanduser().resolve()
    if not exe.exists() or not exe.is_file():
        raise InvalidRequestError(f"EXE 不存在: {exe}")
    if exe.suffix.lower() != ".exe":
        raise InvalidRequestError(f"不是 EXE 文件: {exe}")

    root = exe.parent

    # RPG Maker MV/MZ
    candidates = [
        root / "www" / "data",
        root / "data",
    ]
    for data_dir in candidates:
        if (data_dir / "MapInfos.json").exists():
            return GameDiscoveryResult(engine="mv", data_dir=data_dir.resolve(), archive_path=None)

    # RPG Maker VX Ace (RGSS3)
    data_dir = root / "Data"
    rgss3_archive = root / "Game.rgss3a"
    has_vxace_maps = (data_dir / "MapInfos.rvdata2").exists() or _has_any(data_dir, "Map[0-9][0-9][0-9].rvdata2")
    if rgss3_archive.exists() or has_vxace_maps:
        return GameDiscoveryResult(
            engine="vxace",
            data_dir=data_dir.resolve(),
            archive_path=rgss3_archive.resolve() if rgss3_archive.exists() else None,
        )

    # RPG Maker VX (RGSS2)
    rgss2_archive = root / "Game.rgss2a"
    rgssad_archive = root / "Game.rgssad"
    has_vx_maps = (data_dir / "MapInfos.rvdata").exists() or _has_any(data_dir, "Map[0-9][0-9][0-9].rvdata")
    if rgss2_archive.exists() or rgssad_archive.exists() or has_vx_maps:
        archive_path: Path | None = None
        if rgss2_archive.exists():
            archive_path = rgss2_archive.resolve()
        elif rgssad_archive.exists():
            archive_path = rgssad_archive.resolve()
        return GameDiscoveryResult(engine="vx", data_dir=data_dir.resolve(), archive_path=archive_path)

    raise GameDataInvalidError(
        "未识别到可用游戏数据。"
        "已尝试 MV(data/MapInfos.json)、VX Ace(Data/*.rvdata2 或 Game.rgss3a)、"
        "VX(Data/*.rvdata 或 Game.rgss2a/rgssad)。"
    )


def discover_data_dir_from_exe(exe_path: str | Path) -> Path:
    """Backward-compatible helper used by old call sites/tests."""
    return discover_game_from_exe(exe_path).data_dir
