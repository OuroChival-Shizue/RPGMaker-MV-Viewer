"""HTTP server and API routes for RPGMV Viewer."""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .app_state import AppState
from .assets import AssetResolver
from .encyclopedia import build_encyclopedia
from .errors import (
    GameDataInvalidError,
    InvalidRequestError,
    NoActiveGameError,
    NotFoundError,
    ViewerError,
)
from .file_dialog import pick_exe_file
from .passability import compute_passability
from .paths import PORT, STATIC_DIR


class ViewerRequestHandler(BaseHTTPRequestHandler):
    app_state: AppState | None = None

    def log_message(self, format, *args):  # noqa: A003
        pass

    def _send_json(self, data, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200, content_type: str = "text/plain; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, status: int = 200, content_type: str = "application/octet-stream"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400):
        self._send_json({"error": message}, status=status)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise InvalidRequestError(f"请求体不是有效 JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise InvalidRequestError("请求体必须是 JSON 对象")
        return data

    def _get_state(self) -> AppState:
        if self.app_state is None:
            raise RuntimeError("AppState 未初始化")
        return self.app_state

    def _get_context(self):
        state = self._get_state()
        return state.get_active_context()

    def _serve_static(self, rel_path: str):
        file_path = (STATIC_DIR / rel_path).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self._send_bytes(file_path.read_bytes(), content_type=mime)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/":
                self._serve_static("index.html")
                return
            if path == "/app.js":
                self._serve_static("app.js")
                return
            if path == "/styles.css":
                self._serve_static("styles.css")
                return

            if path == "/api/games":
                self._handle_games_get()
                return
            if path == "/api/cover":
                self._handle_cover(parsed)
                return

            if path == "/api/assets/file":
                self._handle_asset_file(parsed)
                return

            if path == "/api/assets/meta":
                self._handle_asset_meta()
                return

            if path == "/api/tree":
                ctx = self._get_context()
                self._send_json(ctx.db.get_map_tree())
                return

            if path.startswith("/api/map/"):
                try:
                    map_id = int(path.split("/")[-1])
                except ValueError:
                    self._send_error_json("无效的地图ID", status=400)
                    return
                self._handle_map(map_id)
                return

            if path == "/api/search":
                q = parse_qs(parsed.query).get("q", [""])[0].strip()
                if not q:
                    self._send_json([])
                    return
                self._handle_search(q)
                return

            if path.startswith("/api/common_event/"):
                try:
                    ce_id = int(path.split("/")[-1])
                except ValueError:
                    self._send_error_json("无效的公共事件ID", status=400)
                    return
                self._handle_common_event(ce_id)
                return

            if path == "/api/encyclopedia":
                ctx = self._get_context()
                resolver = AssetResolver(ctx.game)
                self._send_json(build_encyclopedia(ctx.db, asset_resolver=resolver))
                return

            if path == "/api/export":
                qs = parse_qs(parsed.query)
                all_flag = (qs.get("all", ["0"])[0] or "0").lower() in ("1", "true", "yes")
                if all_flag:
                    self._handle_export(all_maps=True)
                    return
                map_q = qs.get("map", [""])[0]
                try:
                    map_id = int(map_q)
                except ValueError:
                    self._send_text("缺少或无效的 map 参数", status=400)
                    return
                self._handle_export(map_id=map_id)
                return

            self.send_response(404)
            self.end_headers()
        except NoActiveGameError as exc:
            self._send_error_json(str(exc), status=400)
        except (InvalidRequestError, NotFoundError, GameDataInvalidError) as exc:
            self._send_error_json(str(exc), status=400)
        except ViewerError as exc:
            self._send_error_json(str(exc), status=500)
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(f"服务器异常: {exc}", status=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/games/register-exe":
                self._handle_games_register()
                return
            if path == "/api/games/pick-exe":
                self._handle_games_pick_exe()
                return
            if path == "/api/games/select":
                self._handle_games_select()
                return
            self.send_response(404)
            self.end_headers()
        except (InvalidRequestError, NotFoundError, GameDataInvalidError) as exc:
            self._send_error_json(str(exc), status=400)
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(f"服务器异常: {exc}", status=500)

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith("/api/games/"):
                game_id = path.split("/")[-1].strip()
                if not game_id:
                    raise InvalidRequestError("缺少游戏ID")
                payload = self._read_json_body()
                name = payload.get("name") if "name" in payload else None
                cover_provided = "cover_image" in payload
                cover_image = payload.get("cover_image") if cover_provided else None
                state = self._get_state()
                entry = state.update_game(game_id, name=name, cover_image=cover_image, cover_provided=cover_provided)
                self._send_json({"ok": True, "game": entry.to_dict()})
                return
            self.send_response(404)
            self.end_headers()
        except (InvalidRequestError, NotFoundError) as exc:
            self._send_error_json(str(exc), status=400)
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(f"服务器异常: {exc}", status=500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith("/api/games/"):
                game_id = path.split("/")[-1].strip()
                if not game_id:
                    raise InvalidRequestError("缺少游戏ID")
                state = self._get_state()
                state.delete_game(game_id)
                self._send_json({"ok": True})
                return
            self.send_response(404)
            self.end_headers()
        except (InvalidRequestError, NotFoundError) as exc:
            self._send_error_json(str(exc), status=400)
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(f"服务器异常: {exc}", status=500)

    def _handle_games_get(self):
        state = self._get_state()
        payload = state.registry.as_payload()
        self._send_json(payload)

    def _handle_games_register(self):
        payload = self._read_json_body()
        exe_path = str(payload.get("exe_path", "")).strip()
        name = payload.get("name")
        make_active = bool(payload.get("make_active", False))
        if not exe_path:
            raise InvalidRequestError("缺少 exe_path")
        state = self._get_state()
        entry = state.register_exe(exe_path, name=name, make_active=make_active)
        self._send_json(
            {
                "ok": True,
                "game": entry.to_dict(),
                "games": state.registry.as_payload(),
                "prepare_result": state.get_last_prepare_result(),
            }
        )

    def _handle_games_select(self):
        payload = self._read_json_body()
        game_id = str(payload.get("game_id", "")).strip()
        if not game_id:
            raise InvalidRequestError("缺少 game_id")
        state = self._get_state()
        ctx = state.select_game(game_id)
        self._send_json({"ok": True, "active_game_id": ctx.game.id, "game": ctx.game.to_dict()})

    def _handle_games_pick_exe(self):
        payload = self._read_json_body()
        name = payload.get("name")
        make_active = bool(payload.get("make_active", True))
        exe_path = pick_exe_file()
        if not exe_path:
            self._send_json({"ok": True, "cancelled": True})
            return
        state = self._get_state()
        entry = state.register_exe(exe_path, name=name, make_active=make_active)
        self._send_json(
            {
                "ok": True,
                "cancelled": False,
                "game": entry.to_dict(),
                "games": state.registry.as_payload(),
                "prepare_result": state.get_last_prepare_result(),
            }
        )

    def _handle_cover(self, parsed):
        path_q = parse_qs(parsed.query).get("path", [""])[0].strip()
        if not path_q:
            self.send_response(404)
            self.end_headers()
            return
        local = Path(path_q).expanduser()
        if not local.is_absolute():
            local = local.resolve()
        if not local.exists() or not local.is_file():
            self.send_response(404)
            self.end_headers()
            return
        mime = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
        self._send_bytes(local.read_bytes(), content_type=mime)

    def _handle_map(self, map_id: int):
        ctx = self._get_context()
        resolver = AssetResolver(ctx.game)
        filename = f"Map{map_id:03d}.json"
        map_data = ctx.loader.load_json(filename)
        if map_data is None:
            self._send_error_json(f"无法加载 {filename}", status=400)
            return

        bgm = map_data.get("bgm", {})
        bgm_name = bgm.get("name", "无") if isinstance(bgm, dict) else "无"
        result = {
            "id": map_id,
            "name": ctx.db.get_map_name(map_id),
            "engine": ctx.game.engine,
            "width": map_data.get("width", 0),
            "height": map_data.get("height", 0),
            "bgm": bgm_name,
            "background": resolver.resolve_map_background(map_data, ctx.game.engine),
            "events": [],
        }

        events = map_data.get("events", [])
        ctx.interpreter.set_map_context(map_id, result["name"], map_data)
        for evt in events:
            if evt is not None and isinstance(evt, dict):
                result["events"].append(ctx.interpreter.interpret_event(evt))
        ctx.interpreter.clear_map_context()

        normalized_engine = str(ctx.game.engine or "").lower()
        if normalized_engine in ("mv", "mz", "vx", "vxace"):
            tileset_id = map_data.get("tilesetId", 0)
            tile_data = map_data.get("data", [])
            result["render"] = {
                "tilesetNames": ctx.db.get_tileset_names(tileset_id),
                "data": tile_data if isinstance(tile_data, list) else [],
            }
        if normalized_engine in ("mv", "mz"):
            flags = ctx.db.get_tileset_flags(tileset_id)
            if flags:
                result["passability"] = compute_passability(map_data, flags)

        self._send_json(result)

    def _handle_search(self, keyword: str):
        ctx = self._get_context()
        kw = keyword.lower()
        results = []
        infos = ctx.db.map_infos if isinstance(ctx.db.map_infos, list) else []
        for info in infos:
            if info is None or not isinstance(info, dict):
                continue
            mid = info.get("id", 0)
            mname = info.get("name", f"地图#{mid}")
            map_data = ctx.loader.load_json(f"Map{mid:03d}.json")
            if map_data is None:
                continue
            events = map_data.get("events", [])
            for evt in events:
                if evt is None or not isinstance(evt, dict):
                    continue
                parsed = ctx.interpreter.interpret_event(evt)
                matches = []
                for pg in parsed["pages"]:
                    for cmd in pg["commands"]:
                        if kw in cmd["text"].lower():
                            matches.append(cmd["text"])
                if matches:
                    results.append(
                        {
                            "mapId": mid,
                            "mapName": mname,
                            "eventId": parsed["id"],
                            "eventName": parsed["name"],
                            "x": parsed["x"],
                            "y": parsed["y"],
                            "type": parsed["type"],
                            "matches": matches[:5],
                        }
                    )
        self._send_json(results)

    def _handle_common_event(self, ce_id: int):
        ctx = self._get_context()
        ce = ctx.db.get_common_event(ce_id)
        if ce is None:
            self._send_error_json(f"公共事件 #{ce_id} 不存在", status=400)
            return
        trigger_map = {0: "无", 1: "自动执行", 2: "并行处理"}
        raw_list = ce.get("list", [])
        commands = ctx.interpreter._interpret_commands(raw_list)
        if ctx.interpreter._is_story_page(raw_list):
            for cmd in commands:
                if cmd.get("cls") == "cmd-battle":
                    for ref in cmd.get("refs") or []:
                        if ref.get("kind") in ("troop", "encounter"):
                            ref["special"] = True
                            ref["specialReason"] = "剧情(含对话/选项/脚本)"
        switch_id = ce.get("switchId", 0)
        result = {
            "id": ce_id,
            "name": ce.get("name", ""),
            "trigger": trigger_map.get(ce.get("trigger", 0), "未知"),
            "switchId": switch_id,
            "switchName": ctx.db.get_switch_name(switch_id) if switch_id else "",
            "commands": commands,
        }
        self._send_json(result)

    def _handle_export(self, map_id: int | None = None, all_maps: bool = False):
        ctx = self._get_context()
        if all_maps:
            map_ids = ctx.exporter.get_all_map_ids()
            if not map_ids:
                self._send_text("未找到可导出的地图", status=400)
                return
            md = ctx.exporter.build_export_markdown(map_ids)
            self._send_text(md, content_type="text/markdown; charset=utf-8")
            return

        if not map_id:
            self._send_text("缺少 map 参数", status=400)
            return

        export = ctx.exporter.build_map_export(map_id)
        if not export:
            self._send_text(f"无法加载地图 #{map_id}", status=400)
            return

        md = ctx.exporter.build_export_markdown([map_id])
        self._send_text(md, content_type="text/markdown; charset=utf-8")

    def _handle_asset_file(self, parsed):
        rel_path = parse_qs(parsed.query).get("rel", [""])[0].strip()
        if not rel_path:
            self._send_error_json("缺少 rel 参数", status=400)
            return
        ctx = self._get_context()
        resolver = AssetResolver(ctx.game)
        local = resolver.resolve_rel_asset(rel_path)
        if not local:
            self.send_response(404)
            self.end_headers()
            return
        mime = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
        self._send_bytes(local.read_bytes(), content_type=mime)

    def _handle_asset_meta(self):
        ctx = self._get_context()
        resolver = AssetResolver(ctx.game)
        self._send_json(resolver.build_icon_meta(ctx.game.engine))


def make_server(app_state: AppState, host: str = "127.0.0.1", port: int = PORT) -> HTTPServer:
    handler_cls = type("BoundViewerRequestHandler", (ViewerRequestHandler,), {"app_state": app_state})
    return HTTPServer((host, port), handler_cls)


def run_server(app_state: AppState, host: str = "127.0.0.1", port: int = PORT, open_browser: bool = True) -> None:
    server = make_server(app_state=app_state, host=host, port=port)
    url = f"http://{host}:{port}"
    print(f"\n服务器已启动: {url}")
    print("按 Ctrl+C 停止服务器\n")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止。")
    finally:
        server.server_close()
