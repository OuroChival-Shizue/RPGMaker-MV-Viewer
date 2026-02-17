"""RPG Maker MV event interpreter."""

from __future__ import annotations

from .database import DatabaseManager

class EventInterpreter:
    """将 RPG Maker MV 事件指令翻译为人类可读的结构化数据"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.current_map_id = None
        self.current_map_name = None
        self.current_encounters = None
        self.current_encounter_step = None

    def _classify_event(self, evt):
        """根据事件所有页的指令码自动判定事件类型"""
        codes = set()
        for page in evt.get("pages", []):
            if page is None:
                continue
            for cmd in page.get("list", []):
                c = cmd.get("code", 0)
                p = cmd.get("parameters", [])
                # 125: 金币, 126: 物品, 127: 武器, 128: 防具
                # 只有"增加"操作 (p[1]==0 对于126/127/128, p[0]==0 对于125) 才算宝箱
                if c in (126, 127, 128) and len(p) > 1 and p[1] == 0:
                    codes.add("treasure")
                elif c == 125 and len(p) > 0 and p[0] == 0:
                    codes.add("treasure")
                elif c == 201:
                    codes.add("transfer")
                elif c == 301:
                    codes.add("battle")
                elif c == 101:
                    codes.add("dialog")
        # 按优先级返回
        if "treasure" in codes:
            return "treasure"
        if "transfer" in codes:
            return "transfer"
        if "battle" in codes:
            return "battle"
        if "dialog" in codes:
            return "dialog"
        return "other"

    def interpret_event(self, evt):
        """解析整个事件，返回结构化字典"""
        eid = evt.get("id", "?")
        ename = evt.get("name", "")
        pages = evt.get("pages", [])
        result = {
            "id": eid, "name": ename,
            "x": evt.get("x", 0), "y": evt.get("y", 0),
            "pageCount": len(pages), "pages": [],
            "type": self._classify_event(evt)
        }
        for i, page in enumerate(pages):
            if page is None:
                continue
            result["pages"].append(self._interpret_page(page, i))
        return result

    def _interpret_page(self, page_data, page_index):
        """解析单个事件页"""
        trigger_map = {0: "确定键", 1: "玩家接触", 2: "事件接触",
                       3: "自动执行", 4: "并行处理"}
        trigger = page_data.get("trigger", 0)
        conditions = self._parse_conditions(page_data.get("conditions", {}))
        raw_list = page_data.get("list", [])
        face_name, face_index = self._extract_face_from_commands(raw_list)
        visual = self._parse_page_visual(page_data.get("image", {}), face_name, face_index)
        commands = self._interpret_commands(raw_list)
        if self._is_story_page(raw_list):
            for cmd in commands:
                if cmd.get("cls") == "cmd-battle":
                    for ref in (cmd.get("refs") or []):
                        if ref.get("kind") in ("troop", "encounter"):
                            ref["special"] = True
                            ref["specialReason"] = "剧情(含对话/选项/脚本)"
        return {
            "index": page_index + 1,
            "trigger": trigger_map.get(trigger, f"未知({trigger})"),
            "conditions": conditions,
            "visual": visual,
            "commands": commands
        }

    @staticmethod
    def _extract_face_from_commands(raw_list):
        if not isinstance(raw_list, list):
            return "", 0
        for cmd in raw_list:
            if not isinstance(cmd, dict):
                continue
            if cmd.get("code", 0) != 101:
                continue
            p = cmd.get("parameters", [])
            if not isinstance(p, list):
                continue
            face_name = p[0] if len(p) > 0 else ""
            face_index = p[1] if len(p) > 1 else 0
            if isinstance(face_name, str) and face_name.strip():
                try:
                    return face_name.strip(), int(face_index)
                except Exception:  # noqa: BLE001
                    return face_name.strip(), 0
        return "", 0

    @staticmethod
    def _parse_page_visual(image_data, face_name, face_index):
        if not isinstance(image_data, dict):
            image_data = {}
        character_name = str(
            image_data.get("characterName")
            or image_data.get("character_name")
            or ""
        ).strip()
        raw_index = image_data.get("characterIndex", image_data.get("character_index", 0))
        try:
            character_index = int(raw_index)
        except Exception:  # noqa: BLE001
            character_index = 0
        is_big = bool(image_data.get("isBigCharacter", False))
        if character_name and character_name.startswith("$"):
            is_big = True

        out_face_name = str(face_name or image_data.get("faceName") or image_data.get("face_name") or "").strip()
        if out_face_name:
            out_face_index = int(face_index or image_data.get("faceIndex") or image_data.get("face_index") or 0)
        else:
            out_face_index = 0

        if not character_name and not out_face_name:
            return {}
        try:
            direction = int(image_data.get("direction", image_data.get("characterDirection", 2)) or 2)
        except Exception:  # noqa: BLE001
            direction = 2
        try:
            pattern = int(image_data.get("pattern", image_data.get("characterPattern", 1)) or 1)
        except Exception:  # noqa: BLE001
            pattern = 1
        return {
            "characterName": character_name,
            "characterIndex": character_index,
            "isBigCharacter": is_big,
            "direction": direction,
            "pattern": pattern,
            "faceName": out_face_name,
            "faceIndex": out_face_index,
        }

    def _parse_conditions(self, cond):
        """解析事件页出现条件"""
        texts = []
        if cond.get("switch1Valid"):
            sid = cond.get("switch1Id", 0)
            texts.append(f"开关 [{self.db.get_switch_name(sid)}] = ON")
        if cond.get("switch2Valid"):
            sid = cond.get("switch2Id", 0)
            texts.append(f"开关 [{self.db.get_switch_name(sid)}] = ON")
        if cond.get("variableValid"):
            vid = cond.get("variableId", 0)
            val = cond.get("variableValue", 0)
            texts.append(f"变量 [{self.db.get_variable_name(vid)}] >= {val}")
        if cond.get("selfSwitchValid"):
            texts.append(f"独立开关 {cond.get('selfSwitchCh', 'A')} = ON")
        if cond.get("itemValid"):
            texts.append(f"持有物品 [{self.db.get_item_name(cond.get('itemId', 0))}]")
        if cond.get("actorValid"):
            texts.append(f"角色 #{cond.get('actorId', 0)} 在队伍中")
        return texts

    def _interpret_commands(self, cmd_list):
        """遍历指令列表，逐条翻译"""
        lines = []
        for cmd in cmd_list:
            code = cmd.get("code", 0)
            params = cmd.get("parameters", [])
            indent = cmd.get("indent", 0)
            result = self._translate(code, params)
            if not result:
                continue
            if len(result) == 2:
                text, css_cls = result
                refs = None
            else:
                text, css_cls, refs = result
            if text:
                line = {"indent": indent, "text": text, "cls": css_cls}
                if refs:
                    line["refs"] = refs
                lines.append(line)
        return lines

    def _translate(self, code, p):
        """翻译单条指令，返回 (文本, CSS类名)"""
        # --- 对话 ---
        if code == 101:
            face = p[0] if len(p) > 0 else ""
            pos_map = {0: "上方", 1: "中间", 2: "下方"}
            pos = pos_map.get(p[3], "下方") if len(p) > 3 else "下方"
            tag = f"头像:{face}" if face else ""
            return f"[对话] ({tag} 位置:{pos})", "cmd-talk"
        if code == 401:
            return f"「{p[0]}」" if p else None, "cmd-talk-text"
        # --- 选项 ---
        if code == 102:
            choices = p[0] if p else []
            s = " / ".join(choices) if isinstance(choices, list) else str(choices)
            return f"[选项] {s}", "cmd-choice"
        if code == 402:
            label = p[1] if len(p) > 1 else ""
            return f"[当选择「{label}」时]", "cmd-choice-branch"
        if code == 403:
            return "[当取消时]", "cmd-choice-branch"
        if code == 404:
            return None, ""
        # --- 条件分支 ---
        if code == 111:
            text = self._parse_conditional(p)
            ref = None
            if p and p[0] in (8, 9, 10):
                kind_map = {8: ("items", self.db.get_item_name),
                            9: ("weapons", self.db.get_weapon_name),
                            10: ("armors", self.db.get_armor_name)}
                kind, fn = kind_map.get(p[0], (None, None))
                if kind and fn:
                    iid = p[1] if len(p) > 1 else 0
                    name = fn(iid)
                    ref = self._make_item_ref(kind, iid, name)
            return text, "cmd-cond", [ref] if ref else None
        if code == 411:
            return "[否则]", "cmd-cond"
        if code == 412:
            return None, ""
        # --- 开关 / 变量 / 独立开关 ---
        if code == 121:
            return self._fmt_switch(p), "cmd-switch"
        if code == 122:
            return self._fmt_variable(p), "cmd-var"
        if code == 123:
            ch = p[0] if p else "A"
            v = "ON" if (p[1] if len(p) > 1 else 0) == 0 else "OFF"
            return f"[独立开关] {ch} = {v}", "cmd-switch"
        # --- 金币 ---
        if code == 125:
            return self._fmt_gold(p), "cmd-gold"
        # --- 物品 / 武器 / 防具 ---
        if code == 126:
            text, ref = self._fmt_item(p, "物品", self.db.get_item_name, "items")
            return text, "cmd-item", [ref] if ref else None
        if code == 127:
            text, ref = self._fmt_item(p, "武器", self.db.get_weapon_name, "weapons")
            return text, "cmd-item", [ref] if ref else None
        if code == 128:
            text, ref = self._fmt_item(p, "防具", self.db.get_armor_name, "armors")
            return text, "cmd-item", [ref] if ref else None
        # --- 传送 ---
        if code == 201:
            text, ref = self._fmt_transfer(p)
            return text, "cmd-transfer", [ref] if ref else None
        # --- 输入数值 ---
        if code == 103:
            vid = p[0] if len(p) > 0 else 0
            digits = p[1] if len(p) > 1 else 1
            return f"[输入数值] → 变量[{self.db.get_variable_name(vid)}] (最大{digits}位)", "cmd-misc"
        # --- 选择物品 ---
        if code == 104:
            vid = p[0] if len(p) > 0 else 0
            it_map = {1: "普通物品", 2: "关键物品", 3: "隐藏物品A", 4: "隐藏物品B"}
            it = it_map.get(p[1] if len(p) > 1 else 1, "物品")
            return f"[选择物品] {it} → 变量[{self.db.get_variable_name(vid)}]", "cmd-misc"
        # --- 滚动文本 ---
        if code == 105:
            spd = p[0] if len(p) > 0 else 2
            return f"[滚动文本] (速度:{spd})", "cmd-talk"
        if code == 405:
            return (f"「{p[0]}」" if p else None), "cmd-talk-text"
        # --- 流程控制 ---
        if code == 112:
            return "[循环]", "cmd-cond"
        if code == 413:
            return "[以上反复]", "cmd-cond"
        if code == 113:
            return "[跳出循环]", "cmd-cond"
        if code == 115:
            return "[中断事件处理]", "cmd-cond"
        # --- 计时器 ---
        if code == 124:
            op = p[0] if len(p) > 0 else 0
            if op == 0:
                sec = p[1] if len(p) > 1 else 0
                return f"[计时器] 启动 {sec}秒", "cmd-misc"
            return "[计时器] 停止", "cmd-misc"
        # --- 队伍成员 ---
        if code == 129:
            aid = p[0] if len(p) > 0 else 0
            op = "加入" if (p[1] if len(p) > 1 else 0) == 0 else "离开"
            init = "（初始化）" if (p[2] if len(p) > 2 else 0) == 1 else ""
            return f"[队伍] 角色#{aid} {op}{init}", "cmd-item"
        # --- 其他常见指令 ---
        return self._translate_misc(code, p)

    # --- 格式化辅助方法 ---

    def _fmt_switch(self, p):
        sw_s = p[0] if len(p) > 0 else 0
        sw_e = p[1] if len(p) > 1 else sw_s
        v = "ON" if (p[2] if len(p) > 2 else 0) == 0 else "OFF"
        if sw_s == sw_e:
            return f"[开关] {self.db.get_switch_name(sw_s)} = {v}"
        return f"[开关] {self.db.get_switch_name(sw_s)} ~ {self.db.get_switch_name(sw_e)} = {v}"

    def _fmt_variable(self, p):
        if len(p) < 4:
            return f"[变量] 参数不足"
        vs, ve, op_i, op_t = p[0], p[1], p[2], p[3]
        op_map = {0: "=", 1: "+=", 2: "-=", 3: "*=", 4: "/=", 5: "%="}
        op = op_map.get(op_i, "?=")
        vn = self.db.get_variable_name(vs) if vs == ve else \
            f"{self.db.get_variable_name(vs)} ~ {self.db.get_variable_name(ve)}"
        if op_t == 0:
            return f"[变量] {vn} {op} {p[4] if len(p) > 4 else 0}"
        if op_t == 1:
            return f"[变量] {vn} {op} 变量[{self.db.get_variable_name(p[4] if len(p)>4 else 0)}]"
        if op_t == 2:
            lo = p[4] if len(p) > 4 else 0
            hi = p[5] if len(p) > 5 else 0
            return f"[变量] {vn} {op} 随机({lo}~{hi})"
        return f"[变量] {vn} {op} (类型{op_t})"

    def _fmt_gold(self, p):
        op = p[0] if len(p) > 0 else 0
        op_t = p[1] if len(p) > 1 else 0
        val = p[2] if len(p) > 2 else 0
        sign = "+" if op == 0 else "-"
        if op_t == 0:
            return f"[金币] {sign}{val}"
        return f"[金币] {sign}变量[{self.db.get_variable_name(val)}]的值"

    def _make_item_ref(self, kind, iid, name):
        if not kind or not iid or not name:
            return None
        return {"kind": kind, "id": iid, "name": name}

    def _fmt_item(self, p, label, name_fn, kind):
        iid = p[0] if len(p) > 0 else 0
        op = p[1] if len(p) > 1 else 0
        op_t = p[2] if len(p) > 2 else 0
        val = p[3] if len(p) > 3 else 1
        sign = "+" if op == 0 else "-"
        name = name_fn(iid)
        if op_t == 0:
            text = f"[{label}] {name} x{sign}{val}"
        else:
            text = f"[{label}] {name} x{sign}变量值"
        return text, self._make_item_ref(kind, iid, name)

    def _make_troop_ref(self, troop_id, method, can_escape, can_lose):
        if not troop_id:
            return None
        troop = self.db.get_troop(troop_id)
        name = self.db.get_troop_name(troop_id)
        enemies = []
        if troop and isinstance(troop, dict):
            counts = {}
            hidden = {}
            for m in (troop.get("members") or []):
                if not isinstance(m, dict):
                    continue
                eid = m.get("enemyId", 0)
                if not eid:
                    continue
                counts[eid] = counts.get(eid, 0) + 1
                if m.get("hidden"):
                    hidden[eid] = hidden.get(eid, 0) + 1
            for eid, cnt in counts.items():
                enemies.append({
                    "id": eid,
                    "name": self.db.get_enemy_name(eid),
                    "count": cnt,
                    "hidden": hidden.get(eid, 0)
                })
            enemies.sort(key=lambda x: x["id"])
        method_label = {0: "指定敌群", 1: "变量指定", 2: "随机遇敌"}.get(method, "战斗")
        return {
            "kind": "troop",
            "id": troop_id,
            "name": name,
            "method": method,
            "methodLabel": method_label,
            "canEscape": can_escape,
            "canLose": can_lose,
            "enemies": enemies
        }

    def _make_encounter_ref(self, can_escape=False, can_lose=False):
        if self.current_encounters is None:
            return None
        return {
            "kind": "encounter",
            "name": "随机遇敌",
            "mapId": self.current_map_id,
            "mapName": self.current_map_name,
            "encounterStep": self.current_encounter_step,
            "canEscape": can_escape,
            "canLose": can_lose,
            "encounters": self.current_encounters
        }

    def set_map_context(self, map_id, map_name, map_data):
        self.current_map_id = map_id
        self.current_map_name = map_name
        self.current_encounter_step = map_data.get("encounterStep", None) if isinstance(map_data, dict) else None
        self.current_encounters = self._build_map_encounters(map_data)

    def clear_map_context(self):
        self.current_map_id = None
        self.current_map_name = None
        self.current_encounters = None
        self.current_encounter_step = None

    def _build_map_encounters(self, map_data):
        enc_list = []
        if not isinstance(map_data, dict):
            return enc_list
        for e in (map_data.get("encounterList") or []):
            if not isinstance(e, dict):
                continue
            tid = e.get("troopId", 0)
            if not tid:
                continue
            troop_ref = self._make_troop_ref(tid, 0, False, False)
            enc_list.append({
                "troopId": tid,
                "troopName": self.db.get_troop_name(tid),
                "weight": e.get("weight", 1),
                "regionSet": e.get("regionSet") or [],
                "enemies": troop_ref.get("enemies") if troop_ref else []
            })
        return enc_list

    def _fmt_transfer(self, p):
        method = p[0] if len(p) > 0 else 0
        if method == 0:
            mid = p[1] if len(p) > 1 else 0
            x = p[2] if len(p) > 2 else 0
            y = p[3] if len(p) > 3 else 0
            name = self.db.get_map_name(mid)
            text = f"[传送] → {name}(ID:{mid}) ({x},{y})"
            ref = {"kind": "transfer", "name": name, "mapId": mid, "mapName": name, "x": x, "y": y}
            return text, ref
        return "[传送] → 变量指定位置", None

    def _parse_conditional(self, p):
        """解析条件分支参数"""
        if not p:
            return "[条件] (未知)"
        ct = p[0]
        if ct == 0:  # 开关
            sid = p[1] if len(p) > 1 else 0
            v = "ON" if (p[2] if len(p) > 2 else 0) == 0 else "OFF"
            return f"[条件] 开关[{self.db.get_switch_name(sid)}] == {v}"
        if ct == 1:  # 变量
            vid = p[1] if len(p) > 1 else 0
            cmp_t = p[2] if len(p) > 2 else 0
            cmp_v = p[3] if len(p) > 3 else 0
            op_i = p[4] if len(p) > 4 else 0
            ops = {0: "==", 1: ">=", 2: "<=", 3: ">", 4: "<", 5: "!="}
            vn = self.db.get_variable_name(vid)
            if cmp_t == 0:
                return f"[条件] 变量[{vn}] {ops.get(op_i,'?')} {cmp_v}"
            return f"[条件] 变量[{vn}] {ops.get(op_i,'?')} 变量[{self.db.get_variable_name(cmp_v)}]"
        if ct == 2:  # 独立开关
            ch = p[1] if len(p) > 1 else "A"
            v = "ON" if (p[2] if len(p) > 2 else 0) == 0 else "OFF"
            return f"[条件] 独立开关 {ch} == {v}"
        if ct == 3:  # 计时器
            val = p[1] if len(p) > 1 else 0
            op = ">=" if (p[2] if len(p) > 2 else 0) == 0 else "<="
            return f"[条件] 计时器 {op} {val}秒"
        if ct == 4:  # 角色
            aid = p[1] if len(p) > 1 else 0
            sub = p[2] if len(p) > 2 else 0
            sub_map = {0: "在队伍中", 1: "名字是", 2: "职业是",
                       3: "学会技能", 4: "装备武器", 5: "装备防具", 6: "状态是"}
            extra = f" {p[3]}" if sub >= 1 and len(p) > 3 else ""
            return f"[条件] 角色#{aid} {sub_map.get(sub, '?')}{extra}"
        if ct == 5:  # 敌人 (战斗中)
            eidx = p[1] if len(p) > 1 else 0
            sub = p[2] if len(p) > 2 else 0
            if sub == 0:
                return f"[条件] 敌人#{eidx+1} 出现中"
            return f"[条件] 敌人#{eidx+1} 状态#{p[3] if len(p)>3 else 0}"
        if ct == 6:  # 角色朝向
            char_id = p[1] if len(p) > 1 else 0
            dir_map = {2: "下", 4: "左", 6: "右", 8: "上"}
            d = dir_map.get(p[2] if len(p) > 2 else 0, "?")
            char = "玩家" if char_id == -1 else ("本事件" if char_id == 0 else f"事件#{char_id}")
            return f"[条件] {char} 朝向 {d}"
        if ct == 7:  # 金币
            val = p[1] if len(p) > 1 else 0
            op_map = {0: ">=", 1: "<=", 2: "<"}
            op = op_map.get(p[2] if len(p) > 2 else 0, ">=")
            return f"[条件] 金币 {op} {val}"
        if ct == 8:  # 物品
            iid = p[1] if len(p) > 1 else 0
            return f"[条件] 持有物品[{self.db.get_item_name(iid)}]"
        if ct == 9:  # 武器
            wid = p[1] if len(p) > 1 else 0
            inc = "（含装备）" if (p[2] if len(p) > 2 else 0) else ""
            return f"[条件] 持有武器[{self.db.get_weapon_name(wid)}]{inc}"
        if ct == 10:  # 防具
            aid = p[1] if len(p) > 1 else 0
            inc = "（含装备）" if (p[2] if len(p) > 2 else 0) else ""
            return f"[条件] 持有防具[{self.db.get_armor_name(aid)}]{inc}"
        if ct == 11:  # 按键
            btn_map = {"ok": "确定", "cancel": "取消", "shift": "加速",
                       "down": "下", "left": "左", "right": "右", "up": "上",
                       "pageup": "上一页", "pagedown": "下一页"}
            btn = p[1] if len(p) > 1 else ""
            return f"[条件] 按键「{btn_map.get(btn, btn)}」被按下"
        if ct == 12:  # 脚本
            return f"[条件] 脚本: {p[1] if len(p)>1 else ''}"
        if ct == 13:  # 载具
            v_map = {0: "小舟", 1: "大船", 2: "飞艇"}
            return f"[条件] 乘坐{v_map.get(p[1] if len(p)>1 else 0, '载具')}"
        return f"[条件] 类型{ct}"

    def _translate_misc(self, code, p):
        """翻译其他常见指令"""
        if code == 108:
            return (f"[注释] {p[0]}" if p else None), "cmd-comment"
        if code == 408:
            return (f"  {p[0]}" if p else None), "cmd-comment"
        if code == 117:
            ce_id = p[0] if p else 0
            ce_name = self.db.get_common_event_name(ce_id)
            return f"[公共事件] #{ce_id} 「{ce_name}」", "cmd-common-event"
        if code == 118:
            return (f"[标签] {p[0]}" if p else None), "cmd-misc"
        if code == 119:
            return (f"[跳转] → 标签「{p[0]}」" if p else None), "cmd-misc"
        if code == 230:
            return f"[等待] {p[0] if p else 0} 帧", "cmd-misc"
        if code == 241:
            bgm = p[0] if p else {}
            return (f"[BGM] {bgm.get('name','?')}" if isinstance(bgm, dict) else None), "cmd-misc"
        if code == 245:
            bgs = p[0] if p else {}
            return (f"[BGS] {bgs.get('name','?')}" if isinstance(bgs, dict) else None), "cmd-misc"
        if code == 250:
            se = p[0] if p else {}
            return (f"[SE] {se.get('name','?')}" if isinstance(se, dict) else None), "cmd-misc"
        if code == 301:
            btype = p[0] if len(p) > 0 else 0
            tid = p[1] if len(p) > 1 else 0
            can_escape = bool(p[2]) if len(p) > 2 else False
            can_lose = bool(p[3]) if len(p) > 3 else False
            extra = []
            if can_escape:
                extra.append("可逃跑")
            if can_lose:
                extra.append("可失败")
            extra_s = (" (" + "/".join(extra) + ")") if extra else ""
            if btype == 0:
                tname = self.db.get_troop_name(tid)
                text = f"[战斗] 敌群#{tid}「{tname}」{extra_s}"
                ref = self._make_troop_ref(tid, btype, can_escape, can_lose)
                return text, "cmd-battle", [ref] if ref else None
            if btype == 1:
                vname = self.db.get_variable_name(tid)
                return f"[战斗] 变量指定敌群: 变量[{vname}]{extra_s}", "cmd-battle"
            if btype == 2:
                text = f"[战斗] 随机遇敌{extra_s}"
                ref = self._make_encounter_ref(can_escape, can_lose)
                return text, "cmd-battle", [ref] if ref else None
            return "[战斗] 进入战斗", "cmd-battle"
        if code == 601:
            return "[如果胜利]", "cmd-battle"
        if code == 602:
            return "[如果逃跑]", "cmd-battle"
        if code == 603:
            return "[如果失败]", "cmd-battle"
        if code == 355:
            return (f"[脚本] {p[0]}" if p else None), "cmd-script"
        if code == 655:
            return (f"  {p[0]}" if p else None), "cmd-script"
        if code == 356:
            return (f"[插件] {p[0]}" if p else None), "cmd-script"
        # --- 移动 ---
        if code == 202:
            veh = {0: "小舟", 1: "大船", 2: "飞艇"}.get(p[0] if p else 0, "载具")
            if (p[1] if len(p) > 1 else 0) == 0:
                mid = p[2] if len(p) > 2 else 0
                x = p[3] if len(p) > 3 else 0
                y = p[4] if len(p) > 4 else 0
                return f"[载具位置] {veh} → {self.db.get_map_name(mid)} ({x},{y})", "cmd-transfer"
            return f"[载具位置] {veh} → 变量指定位置", "cmd-transfer"
        if code == 203:
            eid = p[0] if len(p) > 0 else 0
            char = "本事件" if eid == 0 else f"事件#{eid}"
            dt = p[1] if len(p) > 1 else 0
            if dt == 0:
                return f"[设置位置] {char} → ({p[2] if len(p)>2 else 0},{p[3] if len(p)>3 else 0})", "cmd-misc"
            if dt == 1:
                return f"[设置位置] {char} → 变量指定位置", "cmd-misc"
            return f"[设置位置] {char} → 与事件#{p[2] if len(p)>2 else 0}交换", "cmd-misc"
        if code == 204:
            dir_map = {2: "下", 4: "左", 6: "右", 8: "上"}
            d = dir_map.get(p[0] if p else 2, "?")
            dist = p[1] if len(p) > 1 else 0
            return f"[滚动地图] {d} {dist}格", "cmd-misc"
        if code == 205:
            cid = p[0] if len(p) > 0 else 0
            char = "玩家" if cid == -1 else ("本事件" if cid == 0 else f"事件#{cid}")
            return f"[移动路线] {char}", "cmd-misc"
        if code == 505:
            return None, ""  # 移动路线子指令，静默
        if code == 206:
            return "[乘降载具]", "cmd-misc"
        # --- 角色显示 ---
        if code == 211:
            v = "透明" if (p[0] if p else 0) == 0 else "不透明"
            return f"[透明状态] {v}", "cmd-misc"
        if code == 212:
            cid = p[0] if len(p) > 0 else 0
            char = "玩家" if cid == -1 else ("本事件" if cid == 0 else f"事件#{cid}")
            return f"[显示动画] {char} 动画#{p[1] if len(p)>1 else 0}", "cmd-misc"
        if code == 213:
            cid = p[0] if len(p) > 0 else 0
            char = "玩家" if cid == -1 else ("本事件" if cid == 0 else f"事件#{cid}")
            balloon = {1:"感叹",2:"疑问",3:"音符",4:"爱心",5:"愤怒",6:"汗",7:"蛛网",8:"沉默",9:"灯泡",10:"Zzz",11:"自定义1"}
            bn = balloon.get(p[1] if len(p)>1 else 0, f"#{p[1] if len(p)>1 else 0}")
            return f"[气泡图标] {char} {bn}", "cmd-misc"
        if code == 214:
            return "[暂时消除事件]", "cmd-misc"
        if code == 216:
            v = "显示" if (p[0] if p else 0) == 0 else "隐藏"
            return f"[队列跟随] {v}", "cmd-misc"
        if code == 217:
            return "[集合队列]", "cmd-misc"
        # --- 画面效果 ---
        if code == 221:
            return "[淡出画面]", "cmd-misc"
        if code == 222:
            return "[淡入画面]", "cmd-misc"
        if code == 223:
            tone = p[0] if len(p) > 0 and isinstance(p[0], list) else [0,0,0,0]
            dur = p[1] if len(p) > 1 else 0
            return f"[色调变更] ({tone[0]},{tone[1]},{tone[2]},{tone[3]}) {dur}帧", "cmd-misc"
        if code == 224:
            c = p[0] if len(p) > 0 and isinstance(p[0], list) else [255,255,255,170]
            dur = p[1] if len(p) > 1 else 0
            return f"[画面闪烁] ({c[0]},{c[1]},{c[2]},{c[3]}) {dur}帧", "cmd-misc"
        if code == 225:
            pw = p[0] if len(p) > 0 else 0
            sp = p[1] if len(p) > 1 else 0
            dur = p[2] if len(p) > 2 else 0
            return f"[画面震动] 强度:{pw} 速度:{sp} {dur}帧", "cmd-misc"
        # --- 图片 ---
        if code == 231:
            pid = p[0] if len(p) > 0 else 0
            name = p[1] if len(p) > 1 else "?"
            return f"[显示图片] #{pid} {name}", "cmd-misc"
        if code == 232:
            pid = p[0] if len(p) > 0 else 0
            return f"[移动图片] #{pid}", "cmd-misc"
        if code == 233:
            pid = p[0] if len(p) > 0 else 0
            spd = p[1] if len(p) > 1 else 0
            return f"[旋转图片] #{pid} 速度:{spd}", "cmd-misc"
        if code == 234:
            pid = p[0] if len(p) > 0 else 0
            return f"[图片色调] #{pid}", "cmd-misc"
        if code == 235:
            pid = p[0] if len(p) > 0 else 0
            return f"[消除图片] #{pid}", "cmd-misc"
        # --- 音频补充 ---
        if code == 242:
            dur = p[0] if p else 0
            return f"[BGM淡出] {dur}秒", "cmd-misc"
        if code == 243:
            return "[记忆BGM]", "cmd-misc"
        if code == 244:
            return "[恢复BGM]", "cmd-misc"
        if code == 246:
            dur = p[0] if p else 0
            return f"[BGS淡出] {dur}秒", "cmd-misc"
        if code == 251:
            return "[停止SE]", "cmd-misc"
        if code == 261:
            name = p[0] if p else "?"
            return f"[播放影片] {name}", "cmd-misc"
        return self._translate_misc2(code, p)

    def _translate_misc2(self, code, p):
        """翻译系统/地图/角色/商店/战斗指令"""
        # --- 系统设置 ---
        if code == 132:
            bgm = p[0] if p else {}
            return (f"[战斗BGM] {bgm.get('name','?')}" if isinstance(bgm, dict) else "[战斗BGM]"), "cmd-misc"
        if code == 133:
            me = p[0] if p else {}
            return (f"[胜利ME] {me.get('name','?')}" if isinstance(me, dict) else "[胜利ME]"), "cmd-misc"
        if code == 134:
            v = "禁止" if (p[0] if p else 0) == 0 else "允许"
            return f"[存档] {v}", "cmd-misc"
        if code == 135:
            v = "禁止" if (p[0] if p else 0) == 0 else "允许"
            return f"[菜单] {v}", "cmd-misc"
        if code == 136:
            v = "禁止" if (p[0] if p else 0) == 0 else "允许"
            return f"[遇敌] {v}", "cmd-misc"
        if code == 137:
            v = "禁止" if (p[0] if p else 0) == 0 else "允许"
            return f"[队列变更] {v}", "cmd-misc"
        if code == 138:
            c = p[0] if len(p) > 0 and isinstance(p[0], list) else [0,0,0]
            return f"[窗口颜色] ({c[0]},{c[1]},{c[2]})", "cmd-misc"
        if code == 139:
            me = p[0] if p else {}
            return (f"[败北ME] {me.get('name','?')}" if isinstance(me, dict) else "[败北ME]"), "cmd-misc"
        if code == 140:
            veh = {0: "小舟", 1: "大船", 2: "飞艇"}.get(p[0] if p else 0, "载具")
            bgm = p[1] if len(p) > 1 and isinstance(p[1], dict) else {}
            return f"[载具BGM] {veh} {bgm.get('name','?')}", "cmd-misc"
        # --- 地图设置 ---
        if code == 281:
            v = "显示" if (p[0] if p else 0) == 0 else "隐藏"
            return f"[地图名称显示] {v}", "cmd-misc"
        if code == 282:
            return f"[更换图块集] #{p[0] if p else 0}", "cmd-misc"
        if code == 283:
            return f"[更换战斗背景] {p[0] if p else ''} / {p[1] if len(p)>1 else ''}", "cmd-misc"
        if code == 284:
            return f"[更换远景] {p[0] if p else ''}", "cmd-misc"
        # --- 商店 ---
        if code == 302:
            gt = {0: "物品", 1: "武器", 2: "防具"}.get(p[0] if p else 0, "?")
            gid = p[1] if len(p) > 1 else 0
            name_fn = {0: self.db.get_item_name, 1: self.db.get_weapon_name, 2: self.db.get_armor_name}
            fn = name_fn.get(p[0] if p else 0, lambda x: f"#{x}")
            price = ""
            if len(p) > 2 and p[2] == 1:
                price = f" (特价:{p[3] if len(p)>3 else 0})"
            kind_key = {0: "items", 1: "weapons", 2: "armors"}.get(p[0] if p else 0)
            name = fn(gid)
            ref = self._make_item_ref(kind_key, gid, name)
            return f"[商店] {gt}:{name}{price}", "cmd-item", [ref] if ref else None
        if code == 605:
            gt = {0: "物品", 1: "武器", 2: "防具"}.get(p[0] if p else 0, "?")
            gid = p[1] if len(p) > 1 else 0
            name_fn = {0: self.db.get_item_name, 1: self.db.get_weapon_name, 2: self.db.get_armor_name}
            fn = name_fn.get(p[0] if p else 0, lambda x: f"#{x}")
            price = ""
            if len(p) > 2 and p[2] == 1:
                price = f" (特价:{p[3] if len(p)>3 else 0})"
            kind_key = {0: "items", 1: "weapons", 2: "armors"}.get(p[0] if p else 0)
            name = fn(gid)
            ref = self._make_item_ref(kind_key, gid, name)
            return f"  + {gt}:{name}{price}", "cmd-item", [ref] if ref else None
        # --- 名字输入 ---
        if code == 303:
            aid = p[0] if len(p) > 0 else 0
            mx = p[1] if len(p) > 1 else 8
            return f"[名字输入] 角色#{aid} (最大{mx}字)", "cmd-misc"
        # --- 角色属性变更 ---
        if code == 311:
            aid = p[1] if len(p) > 1 else 0
            op = "+" if (p[2] if len(p) > 2 else 0) == 0 else "-"
            val = p[4] if len(p) > 4 else 0
            if (p[3] if len(p) > 3 else 0) == 1:
                val = f"变量[{self.db.get_variable_name(val)}]"
            return f"[HP] 角色#{aid} {op}{val}", "cmd-item"
        if code == 312:
            aid = p[1] if len(p) > 1 else 0
            op = "+" if (p[2] if len(p) > 2 else 0) == 0 else "-"
            val = p[4] if len(p) > 4 else 0
            if (p[3] if len(p) > 3 else 0) == 1:
                val = f"变量[{self.db.get_variable_name(val)}]"
            return f"[MP] 角色#{aid} {op}{val}", "cmd-item"
        if code == 313:
            aid = p[1] if len(p) > 1 else 0
            op = "附加" if (p[2] if len(p) > 2 else 0) == 0 else "解除"
            sid = p[3] if len(p) > 3 else 0
            return f"[状态] 角色#{aid} {op} 状态#{sid}", "cmd-item"
        if code == 314:
            aid = p[1] if len(p) > 1 else 0
            target = "全体" if (p[0] if p else 0) == 0 and aid == 0 else f"角色#{aid}"
            return f"[全回复] {target}", "cmd-item"
        if code == 315:
            aid = p[1] if len(p) > 1 else 0
            op = "+" if (p[2] if len(p) > 2 else 0) == 0 else "-"
            val = p[4] if len(p) > 4 else 0
            if (p[3] if len(p) > 3 else 0) == 1:
                val = f"变量[{self.db.get_variable_name(val)}]"
            return f"[经验] 角色#{aid} {op}{val}", "cmd-item"
        if code == 316:
            aid = p[1] if len(p) > 1 else 0
            op = "+" if (p[2] if len(p) > 2 else 0) == 0 else "-"
            val = p[4] if len(p) > 4 else 0
            if (p[3] if len(p) > 3 else 0) == 1:
                val = f"变量[{self.db.get_variable_name(val)}]"
            return f"[等级] 角色#{aid} {op}{val}", "cmd-item"
        if code == 317:
            aid = p[1] if len(p) > 1 else 0
            param_map = {0:"最大HP",1:"最大MP",2:"攻击力",3:"防御力",4:"魔法攻击",5:"魔法防御",6:"敏捷",7:"幸运"}
            pn = param_map.get(p[2] if len(p)>2 else 0, "?")
            op = "+" if (p[3] if len(p)>3 else 0) == 0 else "-"
            val = p[5] if len(p)>5 else 0
            if (p[4] if len(p)>4 else 0) == 1:
                val = f"变量[{self.db.get_variable_name(val)}]"
            return f"[能力值] 角色#{aid} {pn} {op}{val}", "cmd-item"
        if code == 318:
            aid = p[1] if len(p) > 1 else 0
            op = "习得" if (p[2] if len(p)>2 else 0) == 0 else "遗忘"
            skid = p[3] if len(p) > 3 else 0
            return f"[技能] 角色#{aid} {op} 技能#{skid}", "cmd-item"
        if code == 319:
            aid = p[0] if len(p) > 0 else 0
            etype = {0:"武器",1:"盾牌",2:"头部",3:"身体",4:"饰品"}.get(p[1] if len(p)>1 else 0, "装备")
            eid = p[2] if len(p) > 2 else 0
            if eid == 0:
                return f"[装备] 角色#{aid} 卸下{etype}", "cmd-item"
            return f"[装备] 角色#{aid} {etype}→#{eid}", "cmd-item"
        if code == 320:
            aid = p[0] if len(p) > 0 else 0
            name = p[1] if len(p) > 1 else ""
            return f"[改名] 角色#{aid} → {name}", "cmd-misc"
        if code == 321:
            aid = p[0] if len(p) > 0 else 0
            cid = p[1] if len(p) > 1 else 0
            return f"[转职] 角色#{aid} → 职业#{cid}", "cmd-item"
        if code == 322:
            aid = p[0] if len(p) > 0 else 0
            return f"[更换图像] 角色#{aid}", "cmd-misc"
        if code == 323:
            veh = {0:"小舟",1:"大船",2:"飞艇"}.get(p[0] if p else 0, "载具")
            return f"[更换图像] {veh}", "cmd-misc"
        # --- 战斗中指令 ---
        if code == 331:
            eidx = p[0] if len(p) > 0 else 0
            op = "+" if (p[1] if len(p)>1 else 0) == 0 else "-"
            val = p[3] if len(p)>3 else 0
            if (p[2] if len(p)>2 else 0) == 1:
                val = f"变量[{self.db.get_variable_name(val)}]"
            return f"[敌人HP] #{eidx+1} {op}{val}", "cmd-battle"
        if code == 332:
            eidx = p[0] if len(p) > 0 else 0
            op = "+" if (p[1] if len(p)>1 else 0) == 0 else "-"
            val = p[3] if len(p)>3 else 0
            if (p[2] if len(p)>2 else 0) == 1:
                val = f"变量[{self.db.get_variable_name(val)}]"
            return f"[敌人MP] #{eidx+1} {op}{val}", "cmd-battle"
        if code == 333:
            eidx = p[0] if len(p) > 0 else 0
            op = "附加" if (p[1] if len(p)>1 else 0) == 0 else "解除"
            sid = p[2] if len(p) > 2 else 0
            return f"[敌人状态] #{eidx+1} {op} 状态#{sid}", "cmd-battle"
        if code == 334:
            return f"[敌人全回复] #{(p[0] if p else 0)+1}", "cmd-battle"
        if code == 335:
            return f"[敌人出现] #{(p[0] if p else 0)+1}", "cmd-battle"
        if code == 336:
            eidx = p[0] if len(p) > 0 else 0
            tid = p[1] if len(p) > 1 else 0
            return f"[敌人变身] #{eidx+1} → 敌人#{tid}", "cmd-battle"
        if code == 340:
            return "[中断战斗]", "cmd-battle"
        if code == 342:
            sub = "敌人" if (p[0] if p else 0) == 0 else "角色"
            idx = p[1] if len(p) > 1 else 0
            skid = p[2] if len(p) > 2 else 0
            return f"[强制行动] {sub}#{idx+1} 使用技能#{skid}", "cmd-battle"
        # --- 结束标记 (静默) ---
        if code in (0, 404, 412, 413, 604):
            return None, ""
        return f"[指令 {code}]", "cmd-unknown"

    def _is_story_page(self, cmd_list):
        story_codes = {101, 401, 102, 402, 403, 105, 405, 355, 356}
        for cmd in (cmd_list or []):
            if isinstance(cmd, dict) and cmd.get("code") in story_codes:
                return True
        return False
