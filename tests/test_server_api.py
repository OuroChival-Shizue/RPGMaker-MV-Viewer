from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib import error, request

from viewer.app_state import AppState
from viewer.game_registry import GameRegistry
from viewer.server import make_server


class ServerApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry = GameRegistry(self.root / "games_registry.json")
        self.state = AppState(self.registry)
        self.server = make_server(self.state, host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _get_json(self, path: str):
        with request.urlopen(self._url(path)) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self._url(path),
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8"))

    def _get_bytes(self, path: str):
        with request.urlopen(self._url(path)) as resp:
            return resp.getcode(), resp.read(), dict(resp.headers.items())

    def test_tree_requires_active_game(self):
        with self.assertRaises(error.HTTPError) as ctx:
            self._get_json("/api/tree")
        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertIn("error", payload)

    def test_select_and_tree(self):
        game_root = self.root / "game"
        exe = game_root / "Game.exe"
        data = game_root / "www" / "data"
        data.mkdir(parents=True)
        exe.write_text("", encoding="utf-8")
        (data / "MapInfos.json").write_text("[]", encoding="utf-8")

        self.state.register_exe(str(exe), make_active=True)

        code, games = self._get_json("/api/games")
        self.assertEqual(code, 200)
        self.assertEqual(len(games["games"]), 1)

        code, tree = self._get_json("/api/tree")
        self.assertEqual(code, 200)
        self.assertEqual(tree, [])

        game_id = games["games"][0]["id"]
        code, selected = self._post_json("/api/games/select", {"game_id": game_id})
        self.assertEqual(code, 200)
        self.assertEqual(selected["active_game_id"], game_id)

    def test_register_endpoint_returns_prepare_result(self):
        game_root = self.root / "game2"
        exe = game_root / "Game.exe"
        data = game_root / "www" / "data"
        data.mkdir(parents=True)
        exe.write_text("", encoding="utf-8")
        (data / "MapInfos.json").write_text("[]", encoding="utf-8")
        (data / "System.json").write_text("{}", encoding="utf-8")

        code, resp = self._post_json(
            "/api/games/register-exe",
            {"exe_path": str(exe), "make_active": True},
        )
        self.assertEqual(code, 200)
        self.assertIn("prepare_result", resp)
        self.assertIsInstance(resp["prepare_result"], dict)
        self.assertIn("status", resp["prepare_result"])

    def test_map_background_and_assets_meta(self):
        game_root = self.root / "game3"
        exe = game_root / "Game.exe"
        data = game_root / "www" / "data"
        bg = game_root / "www" / "img" / "parallaxes" / "Forest.png"
        iconset = game_root / "www" / "img" / "system" / "IconSet.png"
        data.mkdir(parents=True)
        bg.parent.mkdir(parents=True)
        iconset.parent.mkdir(parents=True)
        exe.write_text("", encoding="utf-8")
        bg.write_bytes(b"bg")
        iconset.write_bytes(b"icon")

        (data / "MapInfos.json").write_text(
            json.dumps([None, {"id": 1, "name": "Map001", "parentId": 0, "order": 1}]),
            encoding="utf-8",
        )
        (data / "Map001.json").write_text(
            json.dumps(
                {
                    "width": 10,
                    "height": 10,
                    "bgm": {"name": "BgmA"},
                    "parallaxName": "Forest",
                    "events": [],
                    "data": [],
                }
            ),
            encoding="utf-8",
        )

        self.state.register_exe(str(exe), make_active=True)

        code, meta = self._get_json("/api/assets/meta")
        self.assertEqual(code, 200)
        self.assertEqual(meta["engine"], "mv")
        self.assertEqual(meta["icon_size"], 32)
        self.assertTrue(meta["iconset_url"])

        code, mp = self._get_json("/api/map/1")
        self.assertEqual(code, 200)
        self.assertIn("background", mp)
        self.assertEqual(mp["background"]["status"], "found")
        self.assertTrue(mp["background"]["url"])

        code, body, headers = self._get_bytes("/api/assets/file?rel=img/parallaxes/Forest.png")
        self.assertEqual(code, 200)
        self.assertEqual(body, b"bg")
        self.assertIn("no-store", headers.get("Cache-Control", ""))


if __name__ == "__main__":
    unittest.main()
