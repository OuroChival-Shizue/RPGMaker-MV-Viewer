"""Prepare MV/MZ encrypted resources into a local cache directory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_SIGNATURE = "5250474d56000000"
_VERSION = "000301"
_REMAIN = "0000000000"
_FAKE_HEADER = bytes.fromhex(_SIGNATURE + _VERSION + _REMAIN)
_HEADER_LEN = 16

_EXT_MAP = {
    ".rpgmvp": ".png",
    ".rpgmvm": ".m4a",
    ".rpgmvo": ".ogg",
    ".png_": ".png",
    ".m4a_": ".m4a",
    ".ogg_": ".ogg",
}


@dataclass
class PrepareResult:
    status: str
    method: str
    message: str
    output_dir: str
    processed_files: int
    failed_files: int

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "method": self.method,
            "message": self.message,
            "output_dir": self.output_dir,
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
        }


def scan_encrypted_resources(game_root: str | Path) -> list[Path]:
    root = Path(game_root).expanduser().resolve()
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "data_cache" in path.parts:
            continue
        if path.suffix.lower() in _EXT_MAP:
            files.append(path)
    return files


def load_encryption_key(system_json_path: str | Path) -> str | None:
    path = Path(system_json_path).expanduser().resolve()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None

    if not isinstance(raw, dict):
        return None

    key = str(raw.get("encryptionKey", "") or "").strip()
    if not key:
        return None
    if len(key) % 2 != 0:
        return None

    try:
        bytes.fromhex(key)
    except ValueError:
        return None
    return key.lower()


def decrypt_resource_file(src: str | Path, dst: str | Path, key_bytes: bytes, verify_header: bool = True) -> None:
    source = Path(src).expanduser().resolve()
    target = Path(dst).expanduser().resolve()
    content = source.read_bytes()
    if len(content) <= _HEADER_LEN:
        raise ValueError(f"文件过短，无法解密: {source}")

    fake_header = content[:_HEADER_LEN]
    payload = bytearray(content[_HEADER_LEN:])
    if verify_header and fake_header != _FAKE_HEADER:
        raise ValueError(f"文件头校验失败: {source}")

    for i in range(min(_HEADER_LEN, len(payload), len(key_bytes))):
        payload[i] ^= key_bytes[i]

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(bytes(payload))


def _find_system_json(data_dir: Path, game_root: Path) -> Path | None:
    candidates = [
        data_dir / "System.json",
        game_root / "www" / "data" / "System.json",
        game_root / "data" / "System.json",
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _target_path(src: Path, game_root: Path, output_dir: Path) -> Path:
    rel = src.resolve().relative_to(game_root.resolve())
    mapped_ext = _EXT_MAP.get(src.suffix.lower(), src.suffix)
    return (output_dir / rel).with_suffix(mapped_ext)


def prepare_resources(
    game_root: str | Path,
    data_dir: str | Path,
    cache_dir: str | Path,
    java_runner: Callable[[Path, Path], tuple[bool, str]] | None,
) -> PrepareResult:
    root = Path(game_root).expanduser().resolve()
    data = Path(data_dir).expanduser().resolve()
    cache = Path(cache_dir).expanduser().resolve()
    output_dir = (cache / "decrypted").resolve()

    encrypted_files = scan_encrypted_resources(root)
    if not encrypted_files:
        if (root / "nw.pak").exists():
            msg = "检测到 nw.pak，但当前阶段不支持 nw.pak 通用解包。"
        else:
            msg = "未检测到 MV/MZ 加密资源，无需解包。"
        return PrepareResult(
            status="not_needed",
            method="none",
            message=msg,
            output_dir=str(output_dir),
            processed_files=0,
            failed_files=0,
        )

    system_json = _find_system_json(data, root)
    key_text = load_encryption_key(system_json) if system_json else None
    python_error = ""
    processed = 0
    failed = 0

    if key_text:
        key_bytes = bytes.fromhex(key_text)
        for src in encrypted_files:
            dst = _target_path(src, root, output_dir)
            try:
                decrypt_resource_file(src, dst, key_bytes=key_bytes, verify_header=True)
                processed += 1
            except Exception:  # noqa: BLE001
                failed += 1

        if failed == 0:
            return PrepareResult(
                status="python_ok",
                method="python",
                message=f"已使用 Python 解包 {processed} 个资源到缓存。",
                output_dir=str(output_dir),
                processed_files=processed,
                failed_files=failed,
            )

        python_error = f"Python 解包部分失败（成功 {processed} / 失败 {failed}）"
    else:
        python_error = "System.json 缺少 encryptionKey，Python 解包不可用"

    if java_runner is not None:
        ok, msg = java_runner(root, output_dir)
        if ok:
            return PrepareResult(
                status="java_ok",
                method="java",
                message=msg,
                output_dir=str(output_dir),
                processed_files=processed,
                failed_files=failed,
            )
        return PrepareResult(
            status="failed",
            method="none",
            message=f"{python_error}；{msg}",
            output_dir=str(output_dir),
            processed_files=processed,
            failed_files=failed,
        )

    return PrepareResult(
        status="failed",
        method="none",
        message=f"{python_error}；检测到资源封包但无法解包（缺少 Java Decrypter）",
        output_dir=str(output_dir),
        processed_files=processed,
        failed_files=failed,
    )

