# -*- coding: utf-8 -*-
"""RPGMV Viewer entrypoint."""

from __future__ import annotations

import argparse
import sys

from viewer.app_state import AppState
from viewer.game_registry import GameRegistry
from viewer.paths import REGISTRY_PATH
from viewer.server import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RPG Maker 攻略查看器 (MV/VX/VX Ace)")
    parser.add_argument(
        "--register-exe",
        dest="register_exe",
        help="注册游戏 EXE 路径并退出（供 game_tool.bat 调用）",
    )
    parser.add_argument(
        "--name",
        dest="name",
        default=None,
        help="注册时可选名称",
    )
    parser.add_argument(
        "--no-activate",
        dest="no_activate",
        action="store_true",
        help="注册后不切换为当前游戏",
    )
    parser.add_argument(
        "--no-browser",
        dest="no_browser",
        action="store_true",
        help="启动服务时不自动打开浏览器",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    registry = GameRegistry(REGISTRY_PATH)
    state = AppState(registry)

    if args.register_exe:
        try:
            entry = state.register_exe(
                exe_path=args.register_exe,
                name=args.name,
                make_active=(not args.no_activate),
            )
            print("注册成功")
            print(f"  名称: {entry.name}")
            print(f"  引擎: {entry.engine}")
            print(f"  EXE : {entry.exe_path}")
            print(f"  DATA: {entry.data_path}")
            print(f"  ID  : {entry.id}")
            prepare_result = state.get_last_prepare_result()
            if prepare_result:
                print("  资源准备:")
                print(f"    状态: {prepare_result.get('status')}")
                print(f"    方式: {prepare_result.get('method')}")
                print(f"    成功: {prepare_result.get('processed_files')}")
                print(f"    失败: {prepare_result.get('failed_files')}")
                print(f"    缓存: {prepare_result.get('output_dir')}")
                print(f"    信息: {prepare_result.get('message')}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"注册失败: {exc}")
            return 1

    active = registry.get_active_game()
    if active:
        print(f"当前游戏: {active.name}")
        print(f"游戏引擎: {active.engine}")
        print(f"数据目录: {active.data_path}")
    else:
        print("当前未选择游戏，请先拖拽 EXE 到 game_tool.bat 进行注册。")

    run_server(state, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
