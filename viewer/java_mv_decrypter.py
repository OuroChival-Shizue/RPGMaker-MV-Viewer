"""Helpers to call Java-RPG-Maker-MV-Decrypter as a fallback."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def find_java_decrypter_jar(project_root: str | Path) -> Path | None:
    env_path = os.environ.get("RPGMV_JAVA_DECRYPTER_JAR", "").strip()
    if env_path:
        candidate = Path(env_path).expanduser().resolve()
        if candidate.exists() and candidate.is_file():
            return candidate

    root = Path(project_root).expanduser().resolve()
    java_dir = root / "Java-RPG-Maker-MV-Decrypter-master"
    if not java_dir.exists() or not java_dir.is_dir():
        return None

    candidates: list[Path] = []
    for path in java_dir.rglob("*.jar"):
        if "target" not in path.parts:
            continue
        candidates.append(path)

    if not candidates:
        return None

    preferred = [p for p in candidates if "RPG Maker MV Decrypter" in p.name]
    pool = preferred if preferred else candidates
    pool.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return pool[0]


def run_java_decrypt(game_root: str | Path, output_dir: str | Path, jar_path: str | Path | None) -> tuple[bool, str]:
    if not jar_path:
        return False, "检测到资源封包但无法解包（缺少 Java Decrypter JAR）"

    jar = Path(jar_path).expanduser().resolve()
    if not jar.exists() or not jar.is_file():
        return False, f"检测到资源封包但无法解包（JAR 不存在: {jar}）"

    game = Path(game_root).expanduser().resolve()
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    cmd = [
        "java",
        "-jar",
        str(jar),
        "decrypt",
        str(game),
        str(out),
        "false",
        "true",
        "auto",
    ]

    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except FileNotFoundError:
        return False, "检测到资源封包但无法解包（系统未安装 Java）"
    except subprocess.TimeoutExpired:
        return False, "调用 Java 解包超时（>600秒）"
    except Exception as exc:  # noqa: BLE001
        return False, f"调用 Java 解包失败: {exc}"

    if proc.returncode == 0:
        return True, f"已使用 Java 解包到缓存: {out}"

    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    detail = stderr or stdout or f"exit={proc.returncode}"
    detail = detail.splitlines()[-1] if detail else f"exit={proc.returncode}"
    return False, f"Java 解包失败: {detail}"

