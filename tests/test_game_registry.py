from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from viewer.game_registry import GameRegistry


class GameRegistryTest(unittest.TestCase):
    def test_crud_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "games_registry.json"

            game_root = root / "game"
            exe = game_root / "Game.exe"
            data = game_root / "www" / "data"
            data.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")
            (data / "MapInfos.json").write_text("[]", encoding="utf-8")

            reg = GameRegistry(registry_path)
            self.assertTrue(registry_path.exists())
            self.assertEqual(len(reg.list_games()), 0)

            entry = reg.upsert_game(exe, data)
            self.assertEqual(entry.name, "Game")
            self.assertEqual(entry.engine, "mv")
            self.assertEqual(reg.get_active_game_id(), entry.id)

            changed = reg.update_game(entry.id, name="My Game", cover_image="http://example.com/c.png")
            self.assertEqual(changed.name, "My Game")
            self.assertEqual(changed.cover_image, "http://example.com/c.png")

            payload = reg.as_payload()
            self.assertEqual(payload["active_game_id"], entry.id)
            self.assertEqual(len(payload["games"]), 1)
            self.assertEqual(payload["games"][0]["engine"], "mv")

            reg.delete_game(entry.id)
            self.assertEqual(len(reg.list_games()), 0)
            self.assertEqual(reg.get_active_game_id(), "")

    def test_rebuild_when_json_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "games_registry.json"
            registry_path.write_text("{broken json", encoding="utf-8")

            reg = GameRegistry(registry_path)
            payload = reg.as_payload()
            self.assertEqual(payload["games"], [])
            self.assertTrue(payload["warning"])
            backups = list(root.glob("games_registry.broken.*.json"))
            self.assertTrue(backups)

    def test_engine_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "games_registry.json"
            data = root / "Data"
            data.mkdir(parents=True)
            exe = root / "Game.exe"
            exe.write_text("", encoding="utf-8")
            (data / "MapInfos.rvdata2").write_text("x", encoding="utf-8")

            reg = GameRegistry(registry_path)
            entry = reg.upsert_game(exe, data, engine="vxace")
            self.assertEqual(entry.engine, "vxace")

            reg2 = GameRegistry(registry_path)
            loaded = reg2.get_game(entry.id)
            self.assertEqual(loaded.engine, "vxace")


if __name__ == "__main__":
    unittest.main()
