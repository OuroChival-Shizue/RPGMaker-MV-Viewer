from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from viewer.app_state import AppState
from viewer.errors import GameDataInvalidError
from viewer.game_registry import GameRegistry


class AppStateTest(unittest.TestCase):
    def test_select_invalid_game_does_not_override_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = GameRegistry(root / "games_registry.json")

            valid_game = root / "valid"
            valid_exe = valid_game / "Game.exe"
            valid_data = valid_game / "www" / "data"
            valid_data.mkdir(parents=True)
            valid_exe.write_text("", encoding="utf-8")
            (valid_data / "MapInfos.json").write_text("[]", encoding="utf-8")

            invalid_game = root / "invalid"
            invalid_exe = invalid_game / "Game.exe"
            invalid_exe.parent.mkdir(parents=True)
            invalid_exe.write_text("", encoding="utf-8")

            ok_entry = reg.upsert_game(valid_exe, valid_data, name="Valid")
            bad_entry = reg.upsert_game(invalid_exe, invalid_game / "www" / "data", name="Broken")
            reg.set_active_game(ok_entry.id)

            state = AppState(reg)
            self.assertEqual(state.get_active_context().game.id, ok_entry.id)

            with self.assertRaises(GameDataInvalidError):
                state.select_game(bad_entry.id)

            self.assertEqual(reg.get_active_game_id(), ok_entry.id)

    def test_register_uses_system_title_and_auto_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = GameRegistry(root / "games_registry.json")
            state = AppState(reg)

            game_root = root / "my_rpg"
            exe = game_root / "Game.exe"
            data = game_root / "www" / "data"
            title_img = game_root / "www" / "img" / "titles1" / "TitleA.png"
            title_img.parent.mkdir(parents=True)
            data.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")
            (data / "MapInfos.json").write_text("[]", encoding="utf-8")
            (data / "System.json").write_text(
                json.dumps({"gameTitle": "我的游戏", "title1Name": "TitleA"}),
                encoding="utf-8",
            )
            title_img.write_bytes(b"\x89PNG\r\n\x1a\n")

            entry = state.register_exe(str(exe), make_active=True)
            self.assertEqual(entry.name, "我的游戏")
            self.assertEqual(entry.cover_image, str(title_img.resolve()))


if __name__ == "__main__":
    unittest.main()
