from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from viewer.errors import GameDataInvalidError
from viewer.game_discovery import discover_data_dir_from_exe, discover_game_from_exe


class GameDiscoveryTest(unittest.TestCase):
    def test_prefers_www_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "Game.exe"
            exe.write_text("", encoding="utf-8")
            (root / "www" / "data").mkdir(parents=True)
            (root / "www" / "data" / "MapInfos.json").write_text("[]", encoding="utf-8")
            (root / "data").mkdir(parents=True)
            (root / "data" / "MapInfos.json").write_text("[]", encoding="utf-8")

            data = discover_data_dir_from_exe(exe)
            self.assertEqual(data, (root / "www" / "data").resolve())

    def test_falls_back_to_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "Game.exe"
            exe.write_text("", encoding="utf-8")
            (root / "data").mkdir(parents=True)
            (root / "data" / "MapInfos.json").write_text("[]", encoding="utf-8")

            data = discover_data_dir_from_exe(exe)
            self.assertEqual(data, (root / "data").resolve())

    def test_raises_when_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "Game.exe"
            exe.write_text("", encoding="utf-8")
            with self.assertRaises(GameDataInvalidError):
                discover_data_dir_from_exe(exe)

    def test_detects_vxace_by_local_rvdata2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "Game.exe"
            exe.write_text("", encoding="utf-8")
            data = root / "Data"
            data.mkdir(parents=True)
            (data / "MapInfos.rvdata2").write_bytes(b"dummy")

            result = discover_game_from_exe(exe)
            self.assertEqual(result.engine, "vxace")
            self.assertEqual(result.data_dir, data.resolve())
            self.assertIsNone(result.archive_path)

    def test_detects_vxace_by_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "Game.exe"
            exe.write_text("", encoding="utf-8")
            (root / "Game.rgss3a").write_bytes(b"dummy")

            result = discover_game_from_exe(exe)
            self.assertEqual(result.engine, "vxace")
            self.assertEqual(result.archive_path, (root / "Game.rgss3a").resolve())


if __name__ == "__main__":
    unittest.main()
