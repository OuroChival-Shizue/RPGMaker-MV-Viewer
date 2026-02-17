from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from viewer.assets import AssetResolver
from viewer.errors import InvalidRequestError
from viewer.game_registry import GameEntry


def _make_entry(game_root: Path, *, engine: str = "mv") -> GameEntry:
    exe = game_root / "Game.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("", encoding="utf-8")
    return GameEntry(
        id="g1",
        name="Test",
        cover_image="",
        exe_path=str(exe.resolve()),
        data_path=str((game_root / "www" / "data").resolve()),
        engine=engine,
        added_at="",
        updated_at="",
    )


class AssetsTest(unittest.TestCase):
    def test_rejects_unsafe_rel_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = _make_entry(root)
            resolver = AssetResolver(entry)
            with self.assertRaises(InvalidRequestError):
                resolver.resolve_rel_asset("../secret.png")
            with self.assertRaises(InvalidRequestError):
                resolver.resolve_rel_asset("/etc/passwd")

    def test_prefers_decrypted_over_www_and_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = _make_entry(root)

            rel = Path("img/system/IconSet.png")
            www_file = root / "www" / rel
            dec_file = root / "data_cache" / "decrypted" / "www" / rel
            root_file = root / rel
            www_file.parent.mkdir(parents=True, exist_ok=True)
            dec_file.parent.mkdir(parents=True, exist_ok=True)
            root_file.parent.mkdir(parents=True, exist_ok=True)
            root_file.write_bytes(b"root")
            www_file.write_bytes(b"www")
            dec_file.write_bytes(b"dec")

            resolver = AssetResolver(entry)
            found = resolver.resolve_rel_asset("img/system/IconSet.png")
            self.assertIsNotNone(found)
            self.assertEqual(found.read_bytes(), b"dec")

    def test_resolve_map_background_found_missing_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = _make_entry(root)
            resolver = AssetResolver(entry)

            found = resolver.resolve_map_background({}, "mv")
            self.assertEqual(found["status"], "none")

            missing = resolver.resolve_map_background({"parallaxName": "SkyA"}, "mv")
            self.assertEqual(missing["status"], "missing")

            bg = root / "www" / "img" / "parallaxes" / "SkyB.png"
            bg.parent.mkdir(parents=True, exist_ok=True)
            bg.write_bytes(b"png")
            resolver = AssetResolver(entry)
            ok = resolver.resolve_map_background({"parallaxName": "SkyB"}, "mv")
            self.assertEqual(ok["status"], "found")
            self.assertIn("/api/assets/file?rel=", ok["url"])


if __name__ == "__main__":
    unittest.main()
