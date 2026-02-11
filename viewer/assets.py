"""Asset resolving helpers for map backgrounds, icons and portraits."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

from .errors import InvalidRequestError
from .game_registry import GameEntry

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _normalize_rel(rel: str) -> str:
    return str(rel or "").strip().replace("\\", "/")


def asset_url_for_rel(rel: str) -> str:
    return f"/api/assets/file?rel={quote(rel)}"


class AssetResolver:
    """Locate game assets across decrypted cache/www/root directories."""

    def __init__(self, game: GameEntry):
        self.game = game
        self.game_root = Path(game.exe_path).expanduser().resolve().parent
        self.search_roots = self._build_search_roots()

    def _build_search_roots(self) -> list[Path]:
        cache_root = self.game_root / "data_cache" / "decrypted"
        candidates = [
            cache_root / "www",
            cache_root,
            self.game_root / "www",
            self.game_root,
        ]
        existing = [p for p in candidates if p.exists() and p.is_dir()]
        return _dedupe_paths(existing)

    @staticmethod
    def _validate_rel(rel: str) -> PurePosixPath:
        normalized = _normalize_rel(rel)
        if not normalized:
            raise InvalidRequestError("资源相对路径不能为空")
        if normalized.startswith("/"):
            raise InvalidRequestError("资源路径必须为相对路径")
        if len(normalized) >= 2 and normalized[1] == ":":
            raise InvalidRequestError("资源路径不允许使用绝对盘符路径")
        rel_path = PurePosixPath(normalized)
        if rel_path.is_absolute():
            raise InvalidRequestError("资源路径必须为相对路径")
        if any(part == ".." for part in rel_path.parts):
            raise InvalidRequestError("资源路径不允许包含上级目录")
        return rel_path

    def resolve_rel_asset(self, rel: str) -> Path | None:
        rel_path = self._validate_rel(rel)
        for root in self.search_roots:
            candidate = root.joinpath(*rel_path.parts)
            try:
                resolved = candidate.resolve()
                root_resolved = root.resolve()
            except Exception:  # noqa: BLE001
                continue
            if not str(resolved).startswith(str(root_resolved)):
                continue
            if resolved.exists() and resolved.is_file():
                return resolved
        return None

    def _resolve_first_rel(self, rel_candidates: list[str]) -> str | None:
        for rel in rel_candidates:
            normalized = _normalize_rel(rel)
            if not normalized:
                continue
            if self.resolve_rel_asset(normalized):
                return normalized
        return None

    @staticmethod
    def _build_image_candidates(base: str, name: str) -> list[str]:
        nm = str(name or "").strip()
        if not nm:
            return []
        if Path(nm).suffix:
            return [f"{base}/{nm}"]
        out = []
        for ext in _IMAGE_EXTS:
            out.append(f"{base}/{nm}{ext}")
        return out

    def resolve_map_background(self, map_data: dict[str, Any], engine: str) -> dict[str, str]:
        name = str((map_data or {}).get("parallaxName", "") or "").strip()
        if not name:
            return {
                "status": "none",
                "name": "",
                "url": "",
                "message": "当前地图未配置背景材质",
            }

        if engine == "mv":
            bases = ["img/parallaxes"]
        else:
            bases = ["Graphics/Parallaxes", "img/parallaxes"]

        rel_candidates: list[str] = []
        for base in bases:
            rel_candidates.extend(self._build_image_candidates(base, name))
        rel = self._resolve_first_rel(rel_candidates)
        if rel:
            return {
                "status": "found",
                "name": name,
                "url": asset_url_for_rel(rel),
                "message": "背景材质已找到",
            }

        return {
            "status": "missing",
            "name": name,
            "url": "",
            "message": f"找不到背景材质: {name}",
        }

    def build_icon_meta(self, engine: str) -> dict[str, Any]:
        normalized_engine = (engine or "mv").strip().lower()
        if normalized_engine == "mv":
            rel_candidates = [
                "img/system/IconSet.png",
                "img/system/IconSet.jpg",
                "img/system/IconSet.webp",
            ]
            icon_size = 32
        else:
            rel_candidates = [
                "Graphics/System/Iconset.png",
                "Graphics/System/IconSet.png",
                "img/system/IconSet.png",
            ]
            icon_size = 24

        rel = self._resolve_first_rel(rel_candidates)
        return {
            "engine": normalized_engine,
            "iconset_url": asset_url_for_rel(rel) if rel else "",
            "icon_size": icon_size,
            "icon_columns": 16,
        }

    def resolve_enemy_portrait_rel(self, enemy: dict[str, Any]) -> str:
        name = str(enemy.get("battlerName", "") or "").strip()
        if not name:
            return ""

        if self.game.engine == "mv":
            bases = ["img/enemies", "img/sv_enemies"]
        else:
            bases = ["Graphics/Battlers", "img/enemies", "img/sv_enemies"]

        rel_candidates: list[str] = []
        for base in bases:
            rel_candidates.extend(self._build_image_candidates(base, name))
        return self._resolve_first_rel(rel_candidates) or ""
