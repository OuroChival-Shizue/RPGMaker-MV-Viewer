"""Markdown export builder for map/event summaries."""

from __future__ import annotations

from .data_loader import DataLoader
from .database import DatabaseManager
from .interpreter import EventInterpreter


class ExportService:
    def __init__(self, loader: DataLoader, db: DatabaseManager, interpreter: EventInterpreter):
        self.loader = loader
        self.db = db
        self.interpreter = interpreter

    @staticmethod
    def _dedupe(items):
        seen = set()
        out = []
        for it in items:
            if it in seen:
                continue
            seen.add(it)
            out.append(it)
        return out

    def _format_amount(self, op_t, val):
        if op_t == 0:
            return str(val)
        return f"变量[{self.db.get_variable_name(val)}]"

    def _collect_event_export_info(self, evt):
        info = {
            "id": evt.get("id", 0),
            "name": evt.get("name") or "(无名)",
            "x": evt.get("x", 0),
            "y": evt.get("y", 0),
            "has_dialog": False,
            "treasure_items": [],
            "treasure_conditions": [],
            "transfer_targets": [],
            "switch_ops": [],
            "key_item_consumes": [],
        }

        pages = evt.get("pages", []) or []
        for page in pages:
            if page is None or not isinstance(page, dict):
                continue
            conditions = self.interpreter._parse_conditions(page.get("conditions", {}))
            cmd_list = page.get("list", []) or []
            page_treasure = []

            for cmd in cmd_list:
                if not isinstance(cmd, dict):
                    continue
                code = cmd.get("code", 0)
                p = cmd.get("parameters", []) or []

                if code in (101, 401):
                    info["has_dialog"] = True

                if code == 121:
                    sw_s = p[0] if len(p) > 0 else 0
                    sw_e = p[1] if len(p) > 1 else sw_s
                    v = "ON" if (p[2] if len(p) > 2 else 0) == 0 else "OFF"
                    if sw_s == sw_e:
                        name = self.db.get_switch_name(sw_s)
                    else:
                        name = f"{self.db.get_switch_name(sw_s)}~{self.db.get_switch_name(sw_e)}"
                    info["switch_ops"].append(f"{name}={v}")

                if code == 123:
                    ch = p[0] if len(p) > 0 else "A"
                    v = "ON" if (p[1] if len(p) > 1 else 0) == 0 else "OFF"
                    info["switch_ops"].append(f"独立开关{ch}={v}")

                if code == 126 and len(p) > 1 and p[1] == 1:
                    item_id = p[0] if len(p) > 0 else 0
                    if self.db.is_key_item(item_id):
                        amount = self._format_amount(p[2] if len(p) > 2 else 0, p[3] if len(p) > 3 else 0)
                        info["key_item_consumes"].append(f"{self.db.get_item_name(item_id)} x{amount}")

                if code == 201:
                    method = p[0] if len(p) > 0 else 0
                    if method == 0:
                        mid = p[1] if len(p) > 1 else 0
                        x = p[2] if len(p) > 2 else 0
                        y = p[3] if len(p) > 3 else 0
                        mname = self.db.get_map_name(mid)
                        info["transfer_targets"].append(f"{mname} (#{mid}) ({x},{y})")
                    else:
                        info["transfer_targets"].append("变量指定位置")

                if code == 125 and len(p) > 0 and p[0] == 0:
                    op_t = p[1] if len(p) > 1 else 0
                    val = p[2] if len(p) > 2 else 0
                    amount = self._format_amount(op_t, val)
                    page_treasure.append(f"金币 +{amount}")

                if code in (126, 127, 128) and len(p) > 1 and p[1] == 0:
                    item_id = p[0] if len(p) > 0 else 0
                    op_t = p[2] if len(p) > 2 else 0
                    val = p[3] if len(p) > 3 else 0
                    amount = self._format_amount(op_t, val)
                    if code == 126:
                        label = "物品"
                        name = self.db.get_item_name(item_id)
                    elif code == 127:
                        label = "武器"
                        name = self.db.get_weapon_name(item_id)
                    else:
                        label = "防具"
                        name = self.db.get_armor_name(item_id)
                    page_treasure.append(f"{label}: {name} x{amount}")

            if page_treasure and not info["treasure_items"]:
                info["treasure_items"] = page_treasure
                info["treasure_conditions"] = conditions

        info["transfer_targets"] = self._dedupe(info["transfer_targets"])
        info["switch_ops"] = self._dedupe(info["switch_ops"])
        info["key_item_consumes"] = self._dedupe(info["key_item_consumes"])
        return info

    def build_map_export(self, map_id):
        filename = f"Map{map_id:03d}.json"
        map_data = self.loader.load_json(filename)
        if map_data is None:
            return None
        map_name = self.db.get_map_name(map_id)

        treasures = []
        key_events = []
        transfers = []
        npcs = []

        for evt in (map_data.get("events", []) or []):
            if evt is None or not isinstance(evt, dict):
                continue
            info = self._collect_event_export_info(evt)
            is_treasure = bool(info["treasure_items"])
            is_transfer = bool(info["transfer_targets"])
            is_key = bool(info["switch_ops"] or info["key_item_consumes"])

            if is_treasure:
                treasures.append({
                    "name": info["name"],
                    "x": info["x"],
                    "y": info["y"],
                    "items": info["treasure_items"],
                    "conditions": info["treasure_conditions"],
                })
            if is_key:
                key_events.append({
                    "name": info["name"],
                    "x": info["x"],
                    "y": info["y"],
                    "switch_ops": info["switch_ops"],
                    "key_items": info["key_item_consumes"],
                })
            if is_transfer:
                transfers.append({
                    "name": info["name"],
                    "x": info["x"],
                    "y": info["y"],
                    "targets": info["transfer_targets"],
                })
            if info["has_dialog"] and not (is_treasure or is_transfer or is_key):
                npcs.append({"name": info["name"], "x": info["x"], "y": info["y"]})

        return {
            "id": map_id,
            "name": map_name,
            "treasures": treasures,
            "key_events": key_events,
            "transfers": transfers,
            "npcs": npcs,
        }

    def build_export_markdown(self, map_ids):
        lines = ["# 攻略导出", ""]

        for map_id in map_ids:
            export = self.build_map_export(map_id)
            if not export:
                continue
            lines.append(f"## {export['name']} (#{export['id']})")
            lines.append("")

            lines.append("### Treasure (宝箱)")
            if not export["treasures"]:
                lines.append("- 无")
            else:
                for t in export["treasures"]:
                    items = ", ".join(t["items"]) if t["items"] else "未知"
                    conds = "；".join(t["conditions"]) if t["conditions"] else "无"
                    lines.append(f"- ({t['x']},{t['y']}) {t['name']} | {items} | 条件: {conds}")
            lines.append("")

            lines.append("### Key Events (关键事件)")
            if not export["key_events"]:
                lines.append("- 无")
            else:
                for k in export["key_events"]:
                    reasons = []
                    if k["switch_ops"]:
                        reasons.append("开关: " + "; ".join(k["switch_ops"]))
                    if k["key_items"]:
                        reasons.append("消耗: " + ", ".join(k["key_items"]))
                    reason_text = " | ".join(reasons) if reasons else ""
                    line = f"- ({k['x']},{k['y']}) {k['name']}"
                    if reason_text:
                        line += f" | {reason_text}"
                    lines.append(line)
            lines.append("")

            lines.append("### Transfers (传送点)")
            if not export["transfers"]:
                lines.append("- 无")
            else:
                for tr in export["transfers"]:
                    targets = "; ".join(tr["targets"]) if tr["targets"] else "变量指定位置"
                    lines.append(f"- ({tr['x']},{tr['y']}) {tr['name']} -> {targets}")
            lines.append("")

            lines.append("### NPC (普通对话)")
            if not export["npcs"]:
                lines.append("- 无")
            else:
                for n in export["npcs"]:
                    lines.append(f"- ({n['x']},{n['y']}) {n['name']}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def get_all_map_ids(self):
        infos = self.db.map_infos if isinstance(self.db.map_infos, list) else []
        items = []
        seen = set()
        for info in infos:
            if info is None or not isinstance(info, dict):
                continue
            mid = info.get("id", 0)
            if not mid or mid in seen:
                continue
            seen.add(mid)
            items.append((info.get("order", 0), mid))
        items.sort(key=lambda x: (x[0], x[1]))
        return [mid for _, mid in items]

