"""Native file dialog helpers."""

from __future__ import annotations

from .errors import InvalidRequestError


def pick_exe_file() -> str:
    """Open native file picker and return selected exe path or empty string."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # noqa: BLE001
        raise InvalidRequestError("当前环境不支持本地文件选择窗口（tkinter 不可用）") from exc

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected = filedialog.askopenfilename(
            title="选择 RPG Maker 游戏 EXE (MV/VX/VX Ace)",
            filetypes=[("EXE 文件", "*.exe"), ("所有文件", "*.*")],
        )
        root.destroy()
        return selected or ""
    except Exception as exc:  # noqa: BLE001
        raise InvalidRequestError(f"打开文件选择窗口失败: {exc}") from exc
