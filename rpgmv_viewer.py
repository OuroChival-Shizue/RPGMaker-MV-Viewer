# -*- coding: utf-8 -*-
"""
RPG Maker MV 攻略辅助工具 (Web 版)
功能：读取本地 data 文件夹，解析地图和数据库文件，通过浏览器提供可视化交互界面。
核心目标：不打开游戏引擎，上帝视角查看地图上的事件、对话和道具掉落。
"""

import json
import os
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ============================================================
# 全局常量
# ============================================================
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8642


# ============================================================
# 第1部分：数据预处理 (Database Mapping)
# ============================================================

def load_json(filename):
    """安全地加载 JSON 文件，失败时返回 None"""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[警告] 无法加载 {filename}: {e}")
        return None


def build_name_map(json_data, fallback="未知"):
    """从数组型 JSON 构建 {ID: 名称} 映射字典"""
    mapping = {}
    if not isinstance(json_data, list):
        return mapping
    for item in json_data:
        if item is not None and isinstance(item, dict):
            item_id = item.get("id")
            item_name = item.get("name", "").strip()
            if item_id is not None:
                mapping[item_id] = item_name if item_name else f"{fallback}#{item_id}"
    return mapping


def build_switch_var_map(json_array, fallback_prefix=""):
    """从 switches/variables 数组构建 {索引: 名称} 映射"""
    mapping = {}
    if not isinstance(json_array, list):
        return mapping
    for idx, name in enumerate(json_array):
        if idx == 0:
            continue
        if isinstance(name, str) and name.strip():
            mapping[idx] = name.strip()
        else:
            mapping[idx] = f"{fallback_prefix}#{idx}"
    return mapping


class DatabaseManager:
    """数据库管理器：程序启动时加载所有映射表"""

    def __init__(self):
        # 原始数据 (图鉴用)
        self.raw_items = load_json("Items.json") or []
        self.raw_weapons = load_json("Weapons.json") or []
        self.raw_armors = load_json("Armors.json") or []
        self.raw_enemies = load_json("Enemies.json") or []
        self.raw_skills = load_json("Skills.json") or []
        self.raw_states = load_json("States.json") or []
        self.raw_troops = load_json("Troops.json") or []

        # 物品类型映射 (用于识别关键物品)
        self.item_types = {}
        for item in self.raw_items:
            if item is not None and isinstance(item, dict):
                iid = item.get("id")
                if iid is not None:
                    self.item_types[iid] = item.get("itypeId", 1)

        # 名称映射
        self.items = build_name_map(self.raw_items, "未知物品")
        self.weapons = build_name_map(self.raw_weapons, "未知武器")
        self.armors = build_name_map(self.raw_armors, "未知防具")
        self.enemies = build_name_map(self.raw_enemies, "未知敌人")
        self.skills = build_name_map(self.raw_skills, "技能")
        self.states = build_name_map(self.raw_states, "状态")
        self.troops = build_name_map(self.raw_troops, "敌群")

        system_data = load_json("System.json")
        if system_data:
            self.switches = build_switch_var_map(
                system_data.get("switches", []), "开关")
            self.variables = build_switch_var_map(
                system_data.get("variables", []), "变量")
            self.elements = system_data.get("elements", [])
            self.weapon_types = system_data.get("weaponTypes", [])
            self.armor_types = system_data.get("armorTypes", [])
            self.equip_types = system_data.get("equipTypes", [])
            self.skill_types = system_data.get("skillTypes", [])
        else:
            self.switches = {}
            self.variables = {}
            self.elements = []
            self.weapon_types = []
            self.armor_types = []
            self.equip_types = []
            self.skill_types = []

        self.map_infos = load_json("MapInfos.json") or []

        # 公共事件
        self.common_events = load_json("CommonEvents.json") or []
        self.common_event_names = build_name_map(self.common_events, "公共事件")

        # 图块集 (通行度)
        self.tilesets = load_json("Tilesets.json") or []

    def get_item_name(self, item_id):
        return self.items.get(item_id, f"未知物品#{item_id}")

    def is_key_item(self, item_id):
        return self.item_types.get(item_id) == 2

    def get_weapon_name(self, weapon_id):
        return self.weapons.get(weapon_id, f"未知武器#{weapon_id}")

    def get_armor_name(self, armor_id):
        return self.armors.get(armor_id, f"未知防具#{armor_id}")

    def get_enemy_name(self, enemy_id):
        return self.enemies.get(enemy_id, f"敌人#{enemy_id}")

    def get_switch_name(self, switch_id):
        return self.switches.get(switch_id, f"开关#{switch_id}")

    def get_variable_name(self, var_id):
        return self.variables.get(var_id, f"变量#{var_id}")

    def get_map_name(self, map_id):
        if isinstance(self.map_infos, list):
            for info in self.map_infos:
                if info and isinstance(info, dict) and info.get("id") == map_id:
                    return info.get("name", f"地图#{map_id}")
        return f"地图#{map_id}"

    def get_common_event_name(self, ce_id):
        return self.common_event_names.get(ce_id, f"公共事件#{ce_id}")

    def get_common_event(self, ce_id):
        """获取公共事件原始数据"""
        if isinstance(self.common_events, list):
            for ce in self.common_events:
                if ce and isinstance(ce, dict) and ce.get("id") == ce_id:
                    return ce
        return None

    def get_troop_name(self, troop_id):
        return self.troops.get(troop_id, f"敌群#{troop_id}")

    def get_troop(self, troop_id):
        if isinstance(self.raw_troops, list):
            for t in self.raw_troops:
                if t and isinstance(t, dict) and t.get("id") == troop_id:
                    return t
        return None

    def get_tileset_flags(self, tileset_id):
        """获取图块集的通行度标志数组"""
        if isinstance(self.tilesets, list):
            for ts in self.tilesets:
                if ts and isinstance(ts, dict) and ts.get("id") == tileset_id:
                    return ts.get("flags", [])
        return []

    def get_map_tree(self):
        """构建地图树形结构数据，供前端渲染"""
        infos = self.map_infos
        if not isinstance(infos, list):
            return []
        info_dict = {}
        children_map = {}
        for info in infos:
            if info is None or not isinstance(info, dict):
                continue
            mid = info.get("id", 0)
            pid = info.get("parentId", 0)
            info_dict[mid] = info
            children_map.setdefault(pid, []).append(mid)
        for pid in children_map:
            children_map[pid].sort(
                key=lambda x: info_dict.get(x, {}).get("order", 0))

        def build_tree(parent_id):
            nodes = []
            for cid in children_map.get(parent_id, []):
                info = info_dict.get(cid, {})
                nodes.append({
                    "id": cid,
                    "name": info.get("name", f"地图#{cid}"),
                    "children": build_tree(cid)
                })
            return nodes
        return build_tree(0)

    def get_element_name(self, eid):
        if 0 < eid < len(self.elements):
            return self.elements[eid]
        return f"属性#{eid}"

    def get_skill_name(self, sid):
        return self.skills.get(sid, f"技能#{sid}")

    def get_state_name(self, sid):
        return self.states.get(sid, f"状态#{sid}")


# ============================================================
# 第1.5部分：图鉴数据处理
# ============================================================

PARAM_NAMES = ["最大HP", "最大MP", "攻击力", "防御力", "魔法攻击", "魔法防御", "敏捷", "幸运"]
XPARAM_NAMES = ["命中率", "回避率", "暴击率", "暴击回避", "魔法回避", "魔法反射",
                 "反击率", "HP再生", "MP再生", "TP再生"]
SPARAM_NAMES = ["受击率", "防御效果", "恢复效果", "药理知识", "MP消耗率",
                "TP补充率", "物理伤害率", "魔法伤害率", "地形伤害率", "经验获取率"]


def translate_trait(t, db):
    """将单个 trait 翻译为可读文本"""
    code = t.get("code", 0)
    did = t.get("dataId", 0)
    val = t.get("value", 0)
    # 11: 属性有效度
    if code == 11:
        rate = int(val * 100)
        return f"{db.get_element_name(did)}耐性 {rate}%"
    # 12: 弱体有效度
    if code == 12:
        return f"{PARAM_NAMES[did] if did < 8 else '?'}弱体有效度 {int(val*100)}%"
    # 13: 状态有效度
    if code == 13:
        return f"{db.get_state_name(did)}有效度 {int(val*100)}%"
    # 14: 状态免疫
    if code == 14:
        return f"免疫{db.get_state_name(did)}"
    # 21: 通常能力值
    if code == 21:
        return f"{PARAM_NAMES[did] if did < 8 else '?'} ×{int(val*100)}%"
    # 22: 追加能力值
    if code == 22:
        name = XPARAM_NAMES[did] if did < 10 else f"追加能力{did}"
        v = val * 100
        sign = "+" if v >= 0 else ""
        return f"{name}{sign}{v:.0f}%"
    # 23: 特殊能力值
    if code == 23:
        name = SPARAM_NAMES[did] if did < 10 else f"特殊能力{did}"
        return f"{name} ×{int(val*100)}%"
    # 31: 攻击属性
    if code == 31:
        return f"攻击属性:{db.get_element_name(did)}"
    # 32: 攻击状态
    if code == 32:
        return f"攻击附加{db.get_state_name(did)} {int(val*100)}%"
    # 33: 攻击速度补正
    if code == 33:
        return f"攻击速度{'+' if val>=0 else ''}{int(val)}"
    # 34: 攻击追加次数
    if code == 34:
        return f"攻击次数+{int(val)}"
    # 41: 添加技能类型
    if code == 41:
        stn = db.skill_types[did] if did < len(db.skill_types) else f"#{did}"
        return f"可用技能类型:{stn}"
    # 42: 封印技能类型
    if code == 42:
        stn = db.skill_types[did] if did < len(db.skill_types) else f"#{did}"
        return f"封印技能类型:{stn}"
    # 43: 添加技能
    if code == 43:
        return f"习得技能:{db.get_skill_name(did)}"
    # 44: 封印技能
    if code == 44:
        return f"封印技能:{db.get_skill_name(did)}"
    # 51: 装备武器类型
    if code == 51:
        wtn = db.weapon_types[did] if did < len(db.weapon_types) else f"#{did}"
        return f"可装备武器:{wtn}"
    # 52: 装备防具类型
    if code == 52:
        atn = db.armor_types[did] if did < len(db.armor_types) else f"#{did}"
        return f"可装备防具:{atn}"
    # 53: 固定装备
    if code == 53:
        etn = db.equip_types[did] if did < len(db.equip_types) else f"#{did}"
        return f"固定装备:{etn}"
    # 54: 封印装备
    if code == 54:
        etn = db.equip_types[did] if did < len(db.equip_types) else f"#{did}"
        return f"封印装备:{etn}"
    # 55: 槽位类型
    if code == 55:
        return "双持武器" if did == 1 else f"槽位类型{did}"
    # 61: 行动次数追加
    if code == 61:
        return f"行动次数+{int(val*100)}%"
    # 62: 特殊标志
    if code == 62:
        flags = {0: "自动战斗", 1: "防御", 2: "替身", 3: "TP持续"}
        return flags.get(did, f"特殊标志{did}")
    # 63: 消灭效果
    if code == 63:
        effs = {0: "普通", 1: "BOSS", 2: "瞬间消失", 3: "不消失"}
        return f"消灭效果:{effs.get(did, f'#{did}')}"
    # 64: 队伍能力
    if code == 64:
        pabs = {0: "遇敌减半", 1: "无遇敌", 2: "取消偷袭",
                3: "先发制人率提升", 4: "金币双倍", 5: "掉落双倍"}
        return pabs.get(did, f"队伍能力{did}")
    return f"特性[{code},{did},{val}]"


def translate_effect(e, db):
    """将单个 effect (物品使用效果) 翻译为可读文本"""
    code = e.get("code", 0)
    did = e.get("dataId", 0)
    v1 = e.get("value1", 0)
    v2 = e.get("value2", 0)
    if code == 11:  # 恢复HP
        parts = []
        if v1: parts.append(f"{int(v1*100)}%")
        if v2: parts.append(f"{int(v2)}")
        return f"恢复HP {'+'.join(parts)}" if parts else "恢复HP"
    if code == 12:  # 恢复MP
        parts = []
        if v1: parts.append(f"{int(v1*100)}%")
        if v2: parts.append(f"{int(v2)}")
        return f"恢复MP {'+'.join(parts)}" if parts else "恢复MP"
    if code == 13:  # 恢复TP
        return f"恢复TP {int(v1)}"
    if code == 21:  # 附加状态
        return f"附加{db.get_state_name(did)} {int(v1*100)}%"
    if code == 22:  # 解除状态
        return f"解除{db.get_state_name(did)} {int(v1*100)}%"
    if code == 31:  # 强化
        return f"强化{PARAM_NAMES[did] if did<8 else '?'} {int(v1)}回合"
    if code == 32:  # 弱化
        return f"弱化{PARAM_NAMES[did] if did<8 else '?'} {int(v1)}回合"
    if code == 33:  # 解除强化
        return f"解除强化{PARAM_NAMES[did] if did<8 else '?'}"
    if code == 34:  # 解除弱化
        return f"解除弱化{PARAM_NAMES[did] if did<8 else '?'}"
    if code == 41:  # 特殊效果
        return "逃跑" if did == 0 else f"特殊效果{did}"
    if code == 42:  # 成长
        return f"永久{PARAM_NAMES[did] if did<8 else '?'}+{int(v1)}"
    if code == 43:  # 学习技能
        return f"习得{db.get_skill_name(did)}"
    if code == 44:  # 公共事件
        return f"触发公共事件#{did}"
    return f"效果[{code},{did}]"


def build_encyclopedia(db):
    """构建图鉴数据，返回 {weapons, armors, items, enemies}"""
    scope_map = {0: "无", 1: "敌单体", 2: "敌全体", 3: "敌1~2体", 4: "敌2体随机",
                 5: "敌3体随机", 6: "敌4体随机", 7: "友单体", 8: "友全体",
                 9: "友方死亡单体", 10: "友方死亡全体", 11: "使用者"}

    def proc_params(p):
        """将 params[8] 转为非零属性列表"""
        out = []
        for i, v in enumerate(p or []):
            if v != 0 and i < 8:
                out.append({"name": PARAM_NAMES[i], "value": v})
        return out

    def proc_traits(traits):
        return [translate_trait(t, db) for t in (traits or [])]

    # --- 武器 ---
    weapons = []
    for w in db.raw_weapons:
        if not w or not isinstance(w, dict) or not w.get("name", "").strip():
            continue
        wtn = db.weapon_types[w.get("wtypeId", 0)] if w.get("wtypeId", 0) < len(db.weapon_types) else "?"
        weapons.append({
            "id": w["id"], "name": w["name"], "desc": w.get("description", ""),
            "price": w.get("price", 0), "wtype": wtn,
            "params": proc_params(w.get("params")),
            "traits": proc_traits(w.get("traits"))
        })

    # --- 防具 ---
    armors = []
    for a in db.raw_armors:
        if not a or not isinstance(a, dict) or not a.get("name", "").strip():
            continue
        atn = db.armor_types[a.get("atypeId", 0)] if a.get("atypeId", 0) < len(db.armor_types) else "?"
        etn = db.equip_types[a.get("etypeId", 0)] if a.get("etypeId", 0) < len(db.equip_types) else "?"
        armors.append({
            "id": a["id"], "name": a["name"], "desc": a.get("description", ""),
            "price": a.get("price", 0), "atype": atn, "etype": etn,
            "params": proc_params(a.get("params")),
            "traits": proc_traits(a.get("traits"))
        })

    # --- 物品 ---
    items = []
    for it in db.raw_items:
        if not it or not isinstance(it, dict) or not it.get("name", "").strip():
            continue
        itype = {1: "普通物品", 2: "关键物品", 3: "隐藏物品A", 4: "隐藏物品B"}
        items.append({
            "id": it["id"], "name": it["name"], "desc": it.get("description", ""),
            "price": it.get("price", 0),
            "itype": itype.get(it.get("itypeId", 1), "物品"),
            "consumable": it.get("consumable", True),
            "scope": scope_map.get(it.get("scope", 0), "?"),
            "effects": [translate_effect(e, db) for e in (it.get("effects") or [])]
        })

    # --- 怪物 ---
    drop_kind = {1: db.get_item_name, 2: db.get_weapon_name, 3: db.get_armor_name}
    enemies = []
    for en in db.raw_enemies:
        if not en or not isinstance(en, dict) or not en.get("name", "").strip():
            continue
        if en["name"].startswith("ーー"):
            continue
        drops = []
        for d in (en.get("dropItems") or []):
            k = d.get("kind", 0)
            if k == 0:
                continue
            fn = drop_kind.get(k, lambda x: f"#{x}")
            kind_label = {1: "物品", 2: "武器", 3: "防具"}.get(k, "?")
            denom = d.get("denominator", 1)
            rate = f"1/{denom}" if denom > 1 else "100%"
            drops.append(f"{kind_label}:{fn(d.get('dataId', 0))} ({rate})")
        actions = []
        for act in (en.get("actions") or []):
            sid = act.get("skillId", 0)
            r = act.get("rating", 5)
            actions.append({"skill": db.get_skill_name(sid), "rating": r})
        enemies.append({
            "id": en["id"], "name": en["name"],
            "params": proc_params(en.get("params")),
            "exp": en.get("exp", 0), "gold": en.get("gold", 0),
            "drops": drops, "actions": actions,
            "traits": proc_traits(en.get("traits"))
        })

    return {"weapons": weapons, "armors": armors, "items": items, "enemies": enemies}


# ============================================================
# 第2部分：事件解析器 (The Interpreter)
# ============================================================

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
            "commands": commands
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


# 全局数据库和解析器实例（启动时初始化）
db = None
interpreter = None


def _dedupe(items):
    seen = set()
    out = []
    for it in items:
        if it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out


def _format_amount(op_t, val):
    if op_t == 0:
        return str(val)
    return f"变量[{db.get_variable_name(val)}]"


def _collect_event_export_info(evt):
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
        "key_item_consumes": []
    }

    pages = evt.get("pages", []) or []
    for page in pages:
        if page is None or not isinstance(page, dict):
            continue
        conditions = interpreter._parse_conditions(page.get("conditions", {}))
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
                    name = db.get_switch_name(sw_s)
                else:
                    name = f"{db.get_switch_name(sw_s)}~{db.get_switch_name(sw_e)}"
                info["switch_ops"].append(f"{name}={v}")

            if code == 123:
                ch = p[0] if len(p) > 0 else "A"
                v = "ON" if (p[1] if len(p) > 1 else 0) == 0 else "OFF"
                info["switch_ops"].append(f"独立开关{ch}={v}")

            if code == 126 and len(p) > 1 and p[1] == 1:
                item_id = p[0] if len(p) > 0 else 0
                if db.is_key_item(item_id):
                    amount = _format_amount(p[2] if len(p) > 2 else 0,
                                            p[3] if len(p) > 3 else 0)
                    info["key_item_consumes"].append(
                        f"{db.get_item_name(item_id)} x{amount}"
                    )

            if code == 201:
                method = p[0] if len(p) > 0 else 0
                if method == 0:
                    mid = p[1] if len(p) > 1 else 0
                    x = p[2] if len(p) > 2 else 0
                    y = p[3] if len(p) > 3 else 0
                    mname = db.get_map_name(mid)
                    info["transfer_targets"].append(f"{mname} (#{mid}) ({x},{y})")
                else:
                    info["transfer_targets"].append("变量指定位置")

            if code == 125 and len(p) > 0 and p[0] == 0:
                op_t = p[1] if len(p) > 1 else 0
                val = p[2] if len(p) > 2 else 0
                amount = _format_amount(op_t, val)
                page_treasure.append(f"金币 +{amount}")

            if code in (126, 127, 128) and len(p) > 1 and p[1] == 0:
                item_id = p[0] if len(p) > 0 else 0
                op_t = p[2] if len(p) > 2 else 0
                val = p[3] if len(p) > 3 else 0
                amount = _format_amount(op_t, val)
                if code == 126:
                    label = "物品"
                    name = db.get_item_name(item_id)
                elif code == 127:
                    label = "武器"
                    name = db.get_weapon_name(item_id)
                else:
                    label = "防具"
                    name = db.get_armor_name(item_id)
                page_treasure.append(f"{label}: {name} x{amount}")

        if page_treasure and not info["treasure_items"]:
            info["treasure_items"] = page_treasure
            info["treasure_conditions"] = conditions

    info["transfer_targets"] = _dedupe(info["transfer_targets"])
    info["switch_ops"] = _dedupe(info["switch_ops"])
    info["key_item_consumes"] = _dedupe(info["key_item_consumes"])
    return info


def _build_map_export(map_id):
    filename = f"Map{map_id:03d}.json"
    map_data = load_json(filename)
    if map_data is None:
        return None
    map_name = db.get_map_name(map_id)

    treasures = []
    key_events = []
    transfers = []
    npcs = []

    for evt in (map_data.get("events", []) or []):
        if evt is None or not isinstance(evt, dict):
            continue
        info = _collect_event_export_info(evt)
        is_treasure = bool(info["treasure_items"])
        is_transfer = bool(info["transfer_targets"])
        is_key = bool(info["switch_ops"] or info["key_item_consumes"])

        if is_treasure:
            treasures.append({
                "name": info["name"],
                "x": info["x"],
                "y": info["y"],
                "items": info["treasure_items"],
                "conditions": info["treasure_conditions"]
            })
        if is_key:
            key_events.append({
                "name": info["name"],
                "x": info["x"],
                "y": info["y"],
                "switch_ops": info["switch_ops"],
                "key_items": info["key_item_consumes"]
            })
        if is_transfer:
            transfers.append({
                "name": info["name"],
                "x": info["x"],
                "y": info["y"],
                "targets": info["transfer_targets"]
            })
        if info["has_dialog"] and not (is_treasure or is_transfer or is_key):
            npcs.append({
                "name": info["name"],
                "x": info["x"],
                "y": info["y"]
            })

    return {
        "id": map_id,
        "name": map_name,
        "treasures": treasures,
        "key_events": key_events,
        "transfers": transfers,
        "npcs": npcs
    }


def _build_export_markdown(map_ids):
    lines = ["# 攻略导出", ""]

    for map_id in map_ids:
        export = _build_map_export(map_id)
        if not export:
            continue
        lines.append(f"## {export['name']} (#{export['id']})")
        lines.append("")

        # Treasure
        lines.append("### Treasure (宝箱)")
        if not export["treasures"]:
            lines.append("- 无")
        else:
            for t in export["treasures"]:
                items = ", ".join(t["items"]) if t["items"] else "未知"
                conds = "；".join(t["conditions"]) if t["conditions"] else "无"
                lines.append(
                    f"- ({t['x']},{t['y']}) {t['name']} | {items} | 条件: {conds}"
                )
        lines.append("")

        # Key Events
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

        # Transfers
        lines.append("### Transfers (传送点)")
        if not export["transfers"]:
            lines.append("- 无")
        else:
            for tr in export["transfers"]:
                targets = "; ".join(tr["targets"]) if tr["targets"] else "变量指定位置"
                lines.append(
                    f"- ({tr['x']},{tr['y']}) {tr['name']} -> {targets}"
                )
        lines.append("")

        # NPC
        lines.append("### NPC (普通对话)")
        if not export["npcs"]:
            lines.append("- 无")
        else:
            for n in export["npcs"]:
                lines.append(f"- ({n['x']},{n['y']}) {n['name']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _get_all_map_ids():
    infos = db.map_infos if isinstance(db.map_infos, list) else []
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


class RequestHandler(BaseHTTPRequestHandler):
    """处理前端 HTTP 请求"""

    def log_message(self, format, *args):
        """静默日志，避免刷屏"""
        pass

    def _send_json(self, data):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        """发送 HTML 响应"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200, content_type="text/markdown; charset=utf-8"):
        """发送文本响应"""
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 主页
        if path == "/":
            self._send_html(HTML_PAGE)
            return

        # API: 地图树
        if path == "/api/tree":
            self._send_json(db.get_map_tree())
            return

        # API: 加载地图数据
        if path.startswith("/api/map/"):
            try:
                map_id = int(path.split("/")[-1])
            except ValueError:
                self._send_json({"error": "无效的地图ID"})
                return
            self._handle_map(map_id)
            return

        # API: 全局搜索
        if path == "/api/search":
            q = parse_qs(parsed.query).get("q", [""])[0].strip()
            if not q:
                self._send_json([])
                return
            self._handle_search(q)
            return

        # API: 公共事件详情
        if path.startswith("/api/common_event/"):
            try:
                ce_id = int(path.split("/")[-1])
            except ValueError:
                self._send_json({"error": "无效的公共事件ID"})
                return
            self._handle_common_event(ce_id)
            return

        # API: 图鉴数据
        if path == "/api/encyclopedia":
            self._send_json(build_encyclopedia(db))
            return

        # API: 导出攻略 Markdown
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
                self._send_text("缺少或无效的 map 参数", status=400, content_type="text/plain; charset=utf-8")
                return
            self._handle_export(map_id=map_id)
            return

        # 404
        self.send_response(404)
        self.end_headers()

    def _handle_map(self, map_id):
        """处理地图数据请求：返回地图基本信息 + 解析后的事件"""
        filename = f"Map{map_id:03d}.json"
        map_data = load_json(filename)
        if map_data is None:
            self._send_json({"error": f"无法加载 {filename}"})
            return

        # 基本信息
        bgm = map_data.get("bgm", {})
        bgm_name = bgm.get("name", "无") if isinstance(bgm, dict) else "无"
        result = {
            "id": map_id,
            "name": db.get_map_name(map_id),
            "width": map_data.get("width", 0),
            "height": map_data.get("height", 0),
            "bgm": bgm_name,
            "events": []
        }

        # 解析事件
        events = map_data.get("events", [])
        interpreter.set_map_context(map_id, result["name"], map_data)
        for evt in events:
            if evt is not None and isinstance(evt, dict):
                result["events"].append(interpreter.interpret_event(evt))
        interpreter.clear_map_context()

        # 计算通行度
        tileset_id = map_data.get("tilesetId", 0)
        flags = db.get_tileset_flags(tileset_id)
        if flags:
            result["passability"] = compute_passability(map_data, flags)

        self._send_json(result)

    def _handle_search(self, keyword):
        """全局搜索：遍历所有地图，搜索事件指令文本"""
        kw = keyword.lower()
        results = []
        infos = db.map_infos if isinstance(db.map_infos, list) else []
        for info in infos:
            if info is None or not isinstance(info, dict):
                continue
            mid = info.get("id", 0)
            mname = info.get("name", f"地图#{mid}")
            map_data = load_json(f"Map{mid:03d}.json")
            if map_data is None:
                continue
            events = map_data.get("events", [])
            for evt in events:
                if evt is None or not isinstance(evt, dict):
                    continue
                parsed = interpreter.interpret_event(evt)
                matches = []
                for pg in parsed["pages"]:
                    for cmd in pg["commands"]:
                        if kw in cmd["text"].lower():
                            matches.append(cmd["text"])
                if matches:
                    results.append({
                        "mapId": mid, "mapName": mname,
                        "eventId": parsed["id"], "eventName": parsed["name"],
                        "x": parsed["x"], "y": parsed["y"],
                        "type": parsed["type"],
                        "matches": matches[:5]
                    })
        self._send_json(results)

    def _handle_common_event(self, ce_id):
        """处理公共事件详情请求"""
        ce = db.get_common_event(ce_id)
        if ce is None:
            self._send_json({"error": f"公共事件 #{ce_id} 不存在"})
            return
        trigger_map = {0: "无", 1: "自动执行", 2: "并行处理"}
        raw_list = ce.get("list", [])
        commands = interpreter._interpret_commands(raw_list)
        if interpreter._is_story_page(raw_list):
            for cmd in commands:
                if cmd.get("cls") == "cmd-battle":
                    for ref in (cmd.get("refs") or []):
                        if ref.get("kind") in ("troop", "encounter"):
                            ref["special"] = True
                            ref["specialReason"] = "剧情(含对话/选项/脚本)"
        switch_id = ce.get("switchId", 0)
        result = {
            "id": ce_id,
            "name": ce.get("name", ""),
            "trigger": trigger_map.get(ce.get("trigger", 0), "未知"),
            "switchId": switch_id,
            "switchName": db.get_switch_name(switch_id) if switch_id else "",
            "commands": commands
        }
        self._send_json(result)

    def _handle_export(self, map_id=None, all_maps=False):
        """生成攻略 Markdown 文本"""
        if all_maps:
            map_ids = _get_all_map_ids()
            if not map_ids:
                self._send_text("未找到可导出的地图", status=400, content_type="text/plain; charset=utf-8")
                return
            md = _build_export_markdown(map_ids)
            self._send_text(md)
            return
        if not map_id:
            self._send_text("缺少 map 参数", status=400, content_type="text/plain; charset=utf-8")
            return
        export = _build_map_export(map_id)
        if not export:
            self._send_text(f"无法加载地图 #{map_id}", status=400, content_type="text/plain; charset=utf-8")
            return
        md = _build_export_markdown([map_id])
        self._send_text(md)


def compute_passability(map_data, flags):
    """计算地图每个格子的通行度 (基于 RPG Maker MV 逻辑)"""
    w = map_data.get("width", 0)
    h = map_data.get("height", 0)
    data = map_data.get("data", [])
    if not w or not h or not data:
        return []
    layer_size = w * h
    # 结果: 0=不可通行, 1=可通行
    result = []
    for y in range(h):
        for x in range(w):
            passable = False
            for bit in [0x01, 0x02, 0x04, 0x08]:
                if _check_passage(data, flags, x, y, w, h, layer_size, bit):
                    passable = True
                    break
            result.append(1 if passable else 0)
    return result


def _check_passage(data, flags, x, y, w, h, layer_size, bit):
    """模拟 RPG Maker MV 的 Game_Map.checkPassage"""
    for z in range(3, -1, -1):
        idx = z * layer_size + y * w + x
        if idx >= len(data):
            continue
        tile_id = data[idx]
        if tile_id == 0:
            continue
        if tile_id >= len(flags):
            continue
        flag = flags[tile_id]
        if (flag & 0x10) != 0:  # star: 通行，继续检查下层
            continue
        if (flag & bit) == 0:   # 该方向可通行
            return True
        if (flag & bit) == bit: # 该方向不可通行
            return False
    return False


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RPG Maker MV 攻略查看器</title>
<style>
/* ===== 全局重置与基础 ===== */
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0f0f13; --bg2:#16161d; --bg3:#1e1e2a;
  --border:#2a2a3a; --text:#c8c8d8; --text2:#8888a0;
  --accent:#6c5ce7; --accent2:#a29bfe;
  --red:#ff6b6b; --green:#51cf66; --gold:#ffd43b;
  --blue:#74b9ff; --orange:#ffa94d;
}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);
  color:var(--text);height:100vh;overflow:hidden;display:flex;flex-direction:column}
a{color:var(--accent2);text-decoration:none}

/* ===== 顶部标题栏 ===== */
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);
  padding:10px 20px;display:flex;align-items:center;gap:16px;
  border-bottom:1px solid var(--border);flex-shrink:0}
.header h1{font-size:18px;font-weight:600;
  background:linear-gradient(135deg,var(--accent2),var(--gold));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header .info{font-size:12px;color:var(--text2)}
.global-search{display:flex;gap:6px;margin-left:auto;margin-right:12px}
.global-search input{width:280px;padding:5px 10px;border-radius:6px;border:1px solid var(--border);
  background:var(--bg3);color:var(--text);font-size:13px;outline:none;transition:.2s}
.global-search input:focus{border-color:var(--accent);width:340px}
.global-search button{padding:5px 14px;border-radius:6px;border:1px solid var(--accent);
  background:var(--accent);color:#fff;font-size:13px;cursor:pointer;white-space:nowrap}
.global-search button:hover{background:var(--accent2)}

/* ===== 三栏布局 ===== */
.main{display:flex;flex:1;overflow:hidden}

/* --- 左侧地图树 --- */
.sidebar{width:260px;min-width:200px;background:var(--bg2);
  border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0}
.sidebar-header{padding:10px 12px;border-bottom:1px solid var(--border);font-size:13px;
  font-weight:600;color:var(--accent2);text-transform:uppercase;letter-spacing:1px}
.search-box{padding:8px 12px;border-bottom:1px solid var(--border)}
.search-box input{width:100%;padding:6px 10px;border-radius:6px;border:1px solid var(--border);
  background:var(--bg3);color:var(--text);font-size:13px;outline:none;transition:.2s}
.search-box input:focus{border-color:var(--accent)}
.tree-wrap{flex:1;overflow-y:auto;padding:6px 0}
.tree-wrap::-webkit-scrollbar{width:6px}
.tree-wrap::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* 树节点 */
.tree-node{user-select:none}
.tree-label{display:flex;align-items:center;padding:4px 8px;cursor:pointer;
  font-size:13px;border-radius:4px;margin:1px 6px;transition:.15s;gap:4px}
.tree-label:hover{background:var(--bg3)}
.tree-label.active{background:var(--accent);color:#fff}
.tree-label .arrow{width:16px;text-align:center;font-size:10px;color:var(--text2);
  transition:transform .2s;flex-shrink:0}
.tree-label .arrow.open{transform:rotate(90deg)}
.tree-label .arrow.empty{visibility:hidden}
.tree-label .id{color:var(--text2);font-size:11px;margin-right:4px;font-family:monospace}
.tree-children{padding-left:14px;display:none}
.tree-children.open{display:block}

/* --- 中间地图视图 --- */
.map-panel{flex:1;display:flex;flex-direction:column;min-width:0}
.map-toolbar{padding:8px 12px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:12px;font-size:13px;background:var(--bg2)}
.map-toolbar .label{color:var(--text2)}
.map-toolbar .value{color:var(--accent2);font-weight:600}
.zoom-btn{padding:2px 10px;border-radius:4px;border:1px solid var(--border);
  background:var(--bg3);color:var(--text);cursor:pointer;font-size:14px}
.zoom-btn:hover{background:var(--accent);color:#fff}
.toggle-btn{padding:2px 10px;border-radius:4px;border:1px solid var(--border);
  background:var(--bg3);color:var(--text2);cursor:pointer;font-size:12px;transition:.15s}
.toggle-btn:hover{border-color:var(--accent)}
.toggle-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.export-btn{padding:2px 10px;border-radius:4px;border:1px solid var(--accent);
  background:var(--accent);color:#fff;cursor:pointer;font-size:12px;transition:.15s}
.export-btn:hover{background:var(--accent2);border-color:var(--accent2)}
.legend{display:flex;align-items:center;gap:10px;margin-left:auto;font-size:12px}
.legend-item{display:flex;align-items:center;gap:4px}
.legend-dot{width:10px;height:10px;border-radius:2px;flex-shrink:0}
.legend-text{color:var(--text2)}
.map-canvas-wrap{flex:1;overflow:auto;position:relative;background:#0a0a10;cursor:grab}
.map-canvas-wrap.dragging{cursor:grabbing;user-select:none}
.map-canvas-wrap::-webkit-scrollbar{width:8px;height:8px}
.map-canvas-wrap::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}
canvas{display:block}

/* --- 右侧详情面板 --- */
.detail-panel{width:360px;min-width:260px;background:var(--bg2);
  border-left:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0}
.detail-header{padding:10px 12px;border-bottom:1px solid var(--border);
  font-size:13px;font-weight:600;color:var(--accent2);display:flex;align-items:center;gap:8px}
.back-btn{padding:2px 8px;border-radius:4px;border:1px solid var(--border);
  background:var(--bg3);color:var(--text2);cursor:pointer;font-size:12px;transition:.15s;display:none}
.back-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.detail-content{flex:1;overflow-y:auto;padding:12px;font-size:13px;line-height:1.7}
.detail-content::-webkit-scrollbar{width:6px}
.detail-content::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* 详情面板内的样式 */
.info-block{margin-bottom:12px;padding:10px;background:var(--bg3);
  border-radius:8px;border:1px solid var(--border)}
.info-block h3{font-size:13px;color:var(--accent2);margin-bottom:6px;
  padding-bottom:4px;border-bottom:1px solid var(--border)}
.info-row{display:flex;gap:8px;padding:2px 0}
.info-key{color:var(--text2);min-width:60px}
.info-val{color:var(--text);font-weight:500}

/* 事件页标签 */
.page-tabs{display:flex;gap:4px;margin-bottom:8px;flex-wrap:wrap}
.page-tab{padding:4px 12px;border-radius:4px;border:1px solid var(--border);
  background:var(--bg);cursor:pointer;font-size:12px;color:var(--text2);transition:.15s}
.page-tab:hover{border-color:var(--accent)}
.page-tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}

/* 指令行 */
.cmd-line{padding:2px 0;font-family:'Cascadia Code','Fira Code',monospace;font-size:12px}
.cmd-talk{color:#74b9ff}
.cmd-talk-text{color:#dfe6e9;padding-left:12px}
.cmd-choice{color:#ffd43b}
.cmd-choice-branch{color:#fab005}
.cmd-cond{color:#ff922b}
.cmd-switch{color:#a29bfe}
.cmd-var{color:#69db7c}
.cmd-gold{color:#ffd43b;font-weight:600}
.cmd-item{color:#51cf66;font-weight:600}
.cmd-transfer{color:#74b9ff;font-weight:600}
.cmd-battle{color:#ff6b6b}
.cmd-comment{color:#636e72;font-style:italic}
.cmd-script{color:#b2bec3}
.cmd-misc{color:#8888a0}
.cmd-unknown{color:#555}
.cmd-common-event{color:#e599f7;cursor:pointer;text-decoration:underline;text-decoration-style:dotted}
.cmd-common-event:hover{color:#f0abfc}
.ref-link{color:inherit;cursor:pointer;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:2px}
.ref-link:hover{color:var(--accent2)}
.battle-badge{display:inline-block;margin-left:6px;padding:0 6px;border-radius:10px;
  font-size:10px;background:#ffd43b;color:#2f2f2f;vertical-align:1px}
.item-tooltip{position:absolute;z-index:2000;display:none;max-width:280px;
  background:var(--bg2);border:1px solid var(--border);border-radius:8px;
  padding:8px 10px;box-shadow:0 8px 24px rgba(0,0,0,.35);font-size:12px;line-height:1.5}
.item-tip-title{font-weight:600;color:var(--accent2);margin-bottom:4px}
.item-tip-kind{color:var(--text2);font-size:11px;margin-left:6px}
.item-tip-badge{display:inline-block;margin-left:6px;padding:1px 6px;border-radius:10px;
  font-size:10px;background:#ffd43b;color:#2f2f2f}
.item-tip-desc{color:var(--text2);margin:4px 0 6px;white-space:pre-wrap}
.item-tip-row{display:flex;justify-content:space-between;gap:8px;padding:2px 0;border-bottom:1px solid var(--border)}
.item-tip-row .val{color:var(--accent2);font-weight:600}
.item-tip-section{margin-top:6px;padding-top:6px;border-top:1px solid var(--border)}
.item-tip-section-title{font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.item-tip-list div{margin:2px 0}

/* 事件列表 */
.evt-list-item{display:flex;align-items:center;gap:8px;padding:5px 8px;
  border-radius:4px;cursor:pointer;transition:.15s;font-size:12px}
.evt-list-item:hover{background:var(--bg3)}
.evt-list-item .dot{width:8px;height:8px;border-radius:50%;background:var(--red);flex-shrink:0}
.evt-list-item .eid{color:var(--text2);font-family:monospace}
.evt-list-item .ename{color:var(--text)}
.evt-list-item .epos{color:var(--text2);margin-left:auto;font-family:monospace}

/* 搜索结果 */
.search-result{padding:8px 10px;border-radius:6px;border:1px solid var(--border);
  background:var(--bg);margin-bottom:6px;cursor:pointer;transition:.15s}
.search-result:hover{border-color:var(--accent);background:var(--bg3)}
.sr-header{display:flex;align-items:center;gap:6px;margin-bottom:4px}
.sr-map{color:var(--accent2);font-weight:600;font-size:12px}
.sr-evt{color:var(--text);font-size:12px}
.sr-pos{color:var(--text2);font-size:11px;font-family:monospace;margin-left:auto}
.sr-match{color:var(--text2);font-size:11px;padding-left:8px;
  border-left:2px solid var(--border);margin-top:2px;line-height:1.5}

/* 空状态 */
.empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100%;color:var(--text2);gap:8px;font-size:14px}
.empty-state .icon{font-size:48px;opacity:.3}

/* 图鉴 */
.enc-tab{background:var(--bg);color:var(--text2);border:1px solid var(--border);
  padding:5px 14px;border-radius:4px;cursor:pointer;font-size:13px}
.enc-tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.enc-item{padding:8px 12px;border-radius:6px;cursor:pointer;display:flex;
  justify-content:space-between;align-items:center;margin-bottom:2px;font-size:13px}
.enc-item:hover{background:var(--hover)}
.enc-item.sel{background:var(--accent);color:#fff}
.enc-item .eid{color:var(--text2);font-size:11px;font-family:monospace}
.enc-item .price{color:#ffd43b;font-size:11px}
.enc-detail h3{margin:0 0 8px;color:var(--accent2);font-size:16px}
.enc-detail .desc{color:var(--text2);font-size:12px;margin-bottom:10px;line-height:1.6;
  white-space:pre-wrap}
.enc-detail .stat{display:flex;justify-content:space-between;padding:3px 0;
  font-size:12px;border-bottom:1px solid var(--border)}
.enc-detail .stat .val{color:var(--accent2);font-weight:600}
.enc-detail .trait{font-size:12px;color:var(--text);padding:2px 0}
.enc-detail .section{margin-top:10px;padding-top:8px;border-top:1px solid var(--border)}
.enc-detail .section-title{font-size:11px;color:var(--text2);text-transform:uppercase;
  margin-bottom:4px;letter-spacing:1px}
</style>
</head>
<body>

<!-- 顶部标题栏 -->
<div class="header">
  <h1>RPG Maker MV 攻略查看器</h1>
  <div class="global-search">
    <input type="text" id="globalSearchInput" placeholder="全局搜索: 物品名 / 对话内容 / 事件指令...">
    <button id="globalSearchBtn">搜索</button>
  </div>
  <span class="info" id="statusBar">就绪 — 请从左侧选择地图</span>
  <button id="encBtn" onclick="toggleEncyclopedia()" style="background:#6c5ce7;border:none;color:#fff;padding:6px 16px;border-radius:6px;cursor:pointer;font-size:14px;margin-left:8px;">图鉴</button>
</div>

<div class="main">
  <!-- 左侧：地图树 -->
  <div class="sidebar">
    <div class="sidebar-header">地图列表</div>
    <div class="search-box">
      <input type="text" id="searchInput" placeholder="搜索地图名称或ID...">
    </div>
    <div class="tree-wrap" id="treeWrap"></div>
  </div>

  <!-- 中间：地图视图 -->
  <div class="map-panel">
    <div class="map-toolbar">
      <span class="label">地图:</span>
      <span class="value" id="mapTitle">未选择</span>
      <span class="label">尺寸:</span>
      <span class="value" id="mapSize">-</span>
      <span class="label">缩放:</span>
      <button class="zoom-btn" onclick="zoom(-4)">−</button>
      <span class="value" id="zoomLevel">32</span>
      <button class="zoom-btn" onclick="zoom(4)">+</button>
      <button class="toggle-btn" id="passToggle" onclick="togglePassability()">通行度</button>
      <button class="export-btn" onclick="exportGuidePrompt()">导出文本</button>
      <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:#ffd43b"></div><span class="legend-text">$ 宝箱</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#74b9ff"></div><span class="legend-text">&rarr; 传送</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#ff6b6b"></div><span class="legend-text">! 战斗</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#51cf66"></div><span class="legend-text">T 对话</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#636e72"></div><span class="legend-text">&middot; 其他</span></div>
      </div>
    </div>
    <div class="map-canvas-wrap" id="canvasWrap">
      <canvas id="mapCanvas"></canvas>
    </div>
  </div>

  <!-- 右侧：详情面板 -->
  <div class="detail-panel">
    <div class="detail-header">
      <button class="back-btn" id="backBtn" onclick="goBack()">&larr; 返回</button>
      <span>详细信息</span>
    </div>
    <div class="detail-content" id="detailContent">
      <div class="empty-state">
        <div class="icon">&#x1F5FA;</div>
        <div>选择左侧地图开始浏览</div>
      </div>
    </div>
  </div>
</div>

<!-- 图鉴面板 (覆盖层) -->
<div id="encPanel" style="display:none;position:absolute;top:48px;left:0;right:0;bottom:0;background:var(--bg);z-index:100;overflow:hidden;flex-direction:column;">
  <div style="display:flex;gap:4px;padding:8px 16px;background:var(--panel);border-bottom:1px solid var(--border);">
    <button class="enc-tab active" data-tab="weapons" onclick="switchEncTab('weapons')">武器</button>
    <button class="enc-tab" data-tab="armors" onclick="switchEncTab('armors')">防具</button>
    <button class="enc-tab" data-tab="items" onclick="switchEncTab('items')">物品</button>
    <button class="enc-tab" data-tab="enemies" onclick="switchEncTab('enemies')">怪物</button>
    <input type="text" id="encSearch" placeholder="搜索名称..." oninput="filterEnc()" style="margin-left:auto;padding:4px 10px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:4px;width:200px;">
  </div>
  <div style="display:flex;flex:1;overflow:hidden;">
    <div id="encList" style="flex:1;overflow-y:auto;padding:8px;"></div>
    <div id="encDetail" style="width:400px;overflow-y:auto;padding:12px;border-left:1px solid var(--border);background:var(--panel);">
      <div style="color:var(--muted);">点击左侧条目查看详情</div>
    </div>
  </div>
</div>

<div id="itemTooltip" class="item-tooltip"></div>

<script>
// ===== 全局状态 =====
let tileSize = 32;
let mapData = null;      // 当前地图数据
let activeTreeNode = null;
let treeIndex = new Map();
let showPassability = false;
let detailHistory = [];

const canvas = document.getElementById('mapCanvas');
const ctx = canvas.getContext('2d');
const canvasWrap = document.getElementById('canvasWrap');
const itemTooltip = document.getElementById('itemTooltip');

// ===== 详情面板历史 =====
function pushDetail(html) {
  const dc = document.getElementById('detailContent');
  hideItemTooltip();
  if (dc.innerHTML && !dc.innerHTML.includes('empty-state') && !dc.innerHTML.includes('请稍候')) {
    detailHistory.push(dc.innerHTML);
    if (detailHistory.length > 50) detailHistory.shift();
  }
  dc.innerHTML = html;
  document.getElementById('backBtn').style.display = detailHistory.length ? 'inline-block' : 'none';
}
function goBack() {
  if (!detailHistory.length) return;
  const dc = document.getElementById('detailContent');
  dc.innerHTML = detailHistory.pop();
  document.getElementById('backBtn').style.display = detailHistory.length ? 'inline-block' : 'none';
}

// ===== 地图树 =====
async function loadTree() {
  const res = await fetch('/api/tree');
  const tree = await res.json();
  treeIndex = new Map();
  renderTree(tree, document.getElementById('treeWrap'), 0);
}

function renderTree(nodes, container, depth) {
  nodes.forEach(node => {
    const div = document.createElement('div');
    div.className = 'tree-node';

    const label = document.createElement('div');
    label.className = 'tree-label';
    const hasChildren = node.children && node.children.length > 0;

    const arrow = document.createElement('span');
    arrow.className = 'arrow' + (hasChildren ? '' : ' empty');
    arrow.textContent = '\u25B6';

    const idSpan = document.createElement('span');
    idSpan.className = 'id';
    idSpan.textContent = String(node.id).padStart(3, '0');

    const nameSpan = document.createElement('span');
    nameSpan.textContent = node.name;

    label.append(arrow, idSpan, nameSpan);
    div.appendChild(label);
    label.dataset.mapId = String(node.id);
    treeIndex.set(String(node.id), label);

    let childrenDiv = null;
    if (hasChildren) {
      childrenDiv = document.createElement('div');
      childrenDiv.className = 'tree-children';
      renderTree(node.children, childrenDiv, depth + 1);
      div.appendChild(childrenDiv);
    }

    label.addEventListener('click', (e) => {
      e.stopPropagation();
      // 切换展开/折叠
      if (hasChildren) {
        const isOpen = childrenDiv.classList.toggle('open');
        arrow.classList.toggle('open', isOpen);
      }
      // 加载地图
      if (activeTreeNode) activeTreeNode.classList.remove('active');
      label.classList.add('active');
      activeTreeNode = label;
      loadMap(node.id);
    });

    container.appendChild(div);
  });
}

function activateTreeNode(mapId) {
  const key = String(mapId);
  const label = treeIndex.get(key);
  if (!label) return;
  if (activeTreeNode) activeTreeNode.classList.remove('active');
  label.classList.add('active');
  activeTreeNode = label;

  // 展开祖先节点
  let nodeDiv = label.parentElement;
  while (nodeDiv) {
    const parentChildren = nodeDiv.parentElement;
    if (parentChildren && parentChildren.classList.contains('tree-children')) {
      parentChildren.classList.add('open');
      const parentNode = parentChildren.parentElement;
      if (parentNode) {
        const parentLabel = parentNode.querySelector(':scope > .tree-label');
        const arrow = parentLabel && parentLabel.querySelector('.arrow');
        if (arrow) arrow.classList.add('open');
      }
      nodeDiv = parentChildren.parentElement;
    } else {
      break;
    }
  }
  label.scrollIntoView({block: 'nearest'});
}

// ===== 搜索过滤 =====
document.getElementById('searchInput').addEventListener('input', function() {
  const kw = this.value.trim().toLowerCase();
  filterTree(document.getElementById('treeWrap'), kw);
});

function filterTree(container, kw) {
  let hasMatch = false;
  for (const node of container.children) {
    const label = node.querySelector(':scope > .tree-label');
    const children = node.querySelector(':scope > .tree-children');
    const text = label ? label.textContent.toLowerCase() : '';
    let childMatch = false;
    if (children) childMatch = filterTree(children, kw);
    const match = !kw || text.includes(kw) || childMatch;
    node.style.display = match ? '' : 'none';
    if (match && kw && children) {
      children.classList.add('open');
      const arrow = label.querySelector('.arrow');
      if (arrow) arrow.classList.add('open');
    }
    if (match) hasMatch = true;
  }
  return hasMatch;
}

// ===== 地图加载与渲染 =====
async function loadMap(mapId) {
  document.getElementById('statusBar').textContent = '加载中...';
  const res = await fetch('/api/map/' + mapId);
  mapData = await res.json();
  if (mapData.error) {
    document.getElementById('statusBar').textContent = mapData.error;
    return;
  }
  document.getElementById('mapTitle').textContent = mapData.name;
  document.getElementById('mapSize').textContent = mapData.width + ' x ' + mapData.height;
  document.getElementById('statusBar').textContent =
    mapData.name + ' — ' + mapData.events.length + ' 个事件';
  activateTreeNode(mapId);
  renderMap();
  showMapInfo();
}

function focusMapCell(x, y) {
  if (!mapData) return;
  const ts = tileSize;
  const cx = x * ts + ts / 2;
  const cy = y * ts + ts / 2;
  const maxScrollX = Math.max(0, canvas.width - canvasWrap.clientWidth);
  const maxScrollY = Math.max(0, canvas.height - canvasWrap.clientHeight);
  let sx = Math.max(0, cx - canvasWrap.clientWidth / 2);
  let sy = Math.max(0, cy - canvasWrap.clientHeight / 2);
  canvasWrap.scrollLeft = Math.min(maxScrollX, sx);
  canvasWrap.scrollTop = Math.min(maxScrollY, sy);
}

function renderMap() {
  if (!mapData) return;
  const w = mapData.width, h = mapData.height, ts = tileSize;
  canvas.width = w * ts;
  canvas.height = h * ts;

  // 绘制网格底色
  ctx.fillStyle = '#1a1a2e';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#252540';
  ctx.lineWidth = 1;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      ctx.fillStyle = (x + y) % 2 === 0 ? '#1e1e30' : '#1a1a2a';
      ctx.fillRect(x * ts, y * ts, ts, ts);
    }
  }
  // 绘制网格线
  ctx.strokeStyle = '#252540';
  for (let x = 0; x <= w; x++) {
    ctx.beginPath(); ctx.moveTo(x*ts, 0); ctx.lineTo(x*ts, h*ts); ctx.stroke();
  }
  for (let y = 0; y <= h; y++) {
    ctx.beginPath(); ctx.moveTo(0, y*ts); ctx.lineTo(w*ts, y*ts); ctx.stroke();
  }

  // 绘制通行度叠加层
  if (showPassability && mapData.passability) {
    const pass = mapData.passability;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const p = pass[y * w + x];
        if (p === 0) {
          ctx.fillStyle = 'rgba(255,60,60,0.35)';
        } else {
          ctx.fillStyle = 'rgba(60,255,100,0.12)';
        }
        ctx.fillRect(x * ts, y * ts, ts, ts);
      }
    }
  }

  // 事件类型视觉映射
  const EVT_STYLE = {
    treasure: {color:'#ffd43b', glow:'255,212,59', symbol:'$'},
    transfer: {color:'#74b9ff', glow:'116,185,255', symbol:'\u2192'},
    battle:   {color:'#ff6b6b', glow:'255,107,107', symbol:'!'},
    dialog:   {color:'#51cf66', glow:'81,207,102',  symbol:'T'},
    other:    {color:'#636e72', glow:'99,110,114',   symbol:'\u00b7'}
  };

  // 绘制事件标记
  mapData.events.forEach(evt => {
    const ex = evt.x * ts, ey = evt.y * ts;
    const st = EVT_STYLE[evt.type] || EVT_STYLE.other;
    // 发光效果
    const grd = ctx.createRadialGradient(
      ex + ts/2, ey + ts/2, ts*0.1, ex + ts/2, ey + ts/2, ts*0.7);
    grd.addColorStop(0, 'rgba('+st.glow+',0.4)');
    grd.addColorStop(1, 'rgba('+st.glow+',0)');
    ctx.fillStyle = grd;
    ctx.fillRect(ex - ts*0.2, ey - ts*0.2, ts*1.4, ts*1.4);
    // 彩色方块
    ctx.fillStyle = st.color;
    const pad = Math.max(2, ts * 0.12);
    ctx.beginPath();
    roundRect(ctx, ex+pad, ey+pad, ts-pad*2, ts-pad*2, 3);
    ctx.fill();
    // 类型符号
    if (ts >= 16) {
      ctx.fillStyle = evt.type === 'other' ? '#ccc' : '#fff';
      ctx.font = 'bold ' + Math.max(8, ts*0.4|0) + 'px Arial';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(st.symbol, ex + ts/2, ey + ts/2);
    }
  });
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.moveTo(x+r,y);
  ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r);
  ctx.arcTo(x,y,x+w,y,r);
  ctx.closePath();
}

// ===== 缩放 =====
function zoom(delta) {
  tileSize = Math.max(8, Math.min(64, tileSize + delta));
  document.getElementById('zoomLevel').textContent = tileSize;
  renderMap();
}
canvasWrap.addEventListener('wheel', e => {
  e.preventDefault();
  zoom(e.deltaY < 0 ? 4 : -4);
}, {passive: false});

// ===== 通行度开关 =====
function togglePassability() {
  showPassability = !showPassability;
  document.getElementById('passToggle').classList.toggle('active', showPassability);
  renderMap();
}

// ===== 导出攻略 =====
function downloadText(filename, text) {
  const blob = new Blob([text], {type: 'text/markdown;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportGuide(allMaps) {
  const url = allMaps ? '/api/export?all=1' : ('/api/export?map=' + mapData.id);
  document.getElementById('statusBar').textContent = '正在导出...';
  try {
    const res = await fetch(url);
    if (!res.ok) {
      const errText = await res.text();
      alert('导出失败: ' + errText);
      document.getElementById('statusBar').textContent = '导出失败';
      return;
    }
    const text = await res.text();
    const filename = allMaps
      ? 'rpgmv_guide_all.md'
      : ('rpgmv_guide_map_' + String(mapData.id).padStart(3, '0') + '.md');
    downloadText(filename, text);
    document.getElementById('statusBar').textContent = '导出完成';
  } catch (e) {
    alert('导出失败: ' + (e && e.message ? e.message : e));
    document.getElementById('statusBar').textContent = '导出失败';
  }
}

function exportGuidePrompt() {
  const wantAll = confirm('是否导出全部地图？\n确定: 全部地图\n取消: 当前地图');
  if (!wantAll && !mapData) {
    alert('请先选择地图');
    return;
  }
  exportGuide(wantAll);
}

// ===== 拖拽平移 =====
let isDragging = false, wasDragged = false;
let dragStartX = 0, dragStartY = 0, scrollStartX = 0, scrollStartY = 0;

canvasWrap.addEventListener('mousedown', e => {
  if (e.button !== 0) return;
  isDragging = true; wasDragged = false;
  dragStartX = e.clientX; dragStartY = e.clientY;
  scrollStartX = canvasWrap.scrollLeft; scrollStartY = canvasWrap.scrollTop;
  canvasWrap.classList.add('dragging');
});

window.addEventListener('mousemove', e => {
  if (!isDragging) return;
  const dx = e.clientX - dragStartX, dy = e.clientY - dragStartY;
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) wasDragged = true;
  canvasWrap.scrollLeft = scrollStartX - dx;
  canvasWrap.scrollTop = scrollStartY - dy;
});

window.addEventListener('mouseup', () => {
  if (!isDragging) return;
  isDragging = false;
  canvasWrap.classList.remove('dragging');
});

// ===== Canvas 点击 =====
canvas.addEventListener('click', e => {
  if (wasDragged) return;
  if (!mapData) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const gx = Math.floor((e.clientX - rect.left) * scaleX / tileSize);
  const gy = Math.floor((e.clientY - rect.top) * scaleY / tileSize);
  if (gx < 0 || gx >= mapData.width || gy < 0 || gy >= mapData.height) return;

  const evt = mapData.events.find(ev => ev.x === gx && ev.y === gy);
  if (evt) {
    showEventDetail(evt);
  } else {
    pushDetail(
      '<div class="info-block"><h3>空格子</h3>' +
      '<div class="info-row"><span class="info-key">坐标</span>' +
      '<span class="info-val">(' + gx + ', ' + gy + ')</span></div>' +
      '<div style="margin-top:8px;color:var(--text2)">该格子没有事件</div></div>');
  }
});

// ===== 地图信息面板 =====
function showMapInfo() {
  if (!mapData) return;
  const dc = document.getElementById('detailContent');
  let html = '<div class="info-block"><h3>地图信息</h3>';
  html += infoRow('名称', mapData.name);
  html += infoRow('ID', mapData.id);
  html += infoRow('尺寸', mapData.width + ' x ' + mapData.height);
  html += infoRow('BGM', mapData.bgm || '无');
  html += infoRow('事件数', mapData.events.length);
  html += '</div>';

  const TYPE_LABEL = {treasure:'宝箱',transfer:'传送',battle:'战斗',dialog:'对话',other:'其他'};
  const TYPE_COLOR = {treasure:'#ffd43b',transfer:'#74b9ff',battle:'#ff6b6b',dialog:'#51cf66',other:'#636e72'};

  if (mapData.events.length > 0) {
    html += '<div class="info-block"><h3>事件列表 (点击查看详情)</h3>';
    mapData.events.forEach(evt => {
      const tc = TYPE_COLOR[evt.type]||TYPE_COLOR.other;
      const tl = TYPE_LABEL[evt.type]||'其他';
      html += '<div class="evt-list-item" onclick="showEventDetail(mapData.events.find(e=>e.id==' + evt.id + '))">';
      html += '<span class="dot" style="background:'+tc+'"></span>';
      html += '<span class="eid">#' + String(evt.id).padStart(3,'0') + '</span>';
      html += '<span class="etype" style="color:'+tc+'">['+tl+']</span>';
      html += '<span class="ename">' + esc(evt.name) + '</span>';
      html += '<span class="epos">(' + evt.x + ',' + evt.y + ')</span>';
      html += '</div>';
    });
    html += '</div>';
  }
  pushDetail(html);
}

function infoRow(key, val) {
  return '<div class="info-row"><span class="info-key">' + key +
    '</span><span class="info-val">' + esc(String(val)) + '</span></div>';
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderCmdText(cmd) {
  let text = cmd.text || '';
  if (!cmd.refs || !cmd.refs.length) return esc(text);
  let html = esc(text);
  cmd.refs.forEach(ref => {
    if (!ref || !ref.name) return;
    const safeName = esc(ref.name);
    let link = '';
    if (ref.kind === 'troop') {
      const payload = encodeURIComponent(JSON.stringify(ref));
      const badge = ref.special ? '<span class="battle-badge">剧情</span>' : '';
      link = '<span class="ref-link" data-kind="troop" data-ref="' + payload + '">' + safeName + '</span>' + badge;
    } else if (ref.kind === 'encounter') {
      const payload = encodeURIComponent(JSON.stringify(ref));
      const badge = ref.special ? '<span class="battle-badge">剧情</span>' : '';
      link = '<span class="ref-link" data-kind="encounter" data-ref="' + payload + '">' + safeName + '</span>' + badge;
    } else if (ref.kind === 'transfer') {
      link = '<span class="ref-link" data-kind="transfer" data-map="' + ref.mapId +
        '" data-x="' + ref.x + '" data-y="' + ref.y + '">' + safeName + '</span>';
    } else {
      link = '<span class="ref-link" data-kind="' + ref.kind +
        '" data-id="' + ref.id + '">' + safeName + '</span>';
    }
    html = html.replace(safeName, link);
  });
  return html;
}

function hideItemTooltip() {
  if (itemTooltip) itemTooltip.style.display = 'none';
}

async function ensureEncData() {
  if (encData) return;
  const res = await fetch('/api/encyclopedia');
  encData = await res.json();
}

function findEncItem(kind, id) {
  const list = (encData && encData[kind]) ? encData[kind] : [];
  return list.find(x => x.id === id);
}

function buildItemTipHtml(kind, item) {
  const kindLabel = {items:'物品', weapons:'武器', armors:'防具'}[kind] || kind;
  if (!item) return '<div style="color:var(--text2)">未找到条目</div>';
  let h = '<div class="item-tip-title">#' + item.id + ' ' + esc(item.name) +
    '<span class="item-tip-kind">[' + kindLabel + ']</span></div>';
  if (item.desc) h += '<div class="item-tip-desc">' + esc(item.desc) + '</div>';

  if (kind === 'weapons') {
    h += '<div class="item-tip-row"><span>类型</span><span class="val">' + esc(item.wtype) + '</span></div>';
  } else if (kind === 'armors') {
    h += '<div class="item-tip-row"><span>防具类型</span><span class="val">' + esc(item.atype) + '</span></div>';
    h += '<div class="item-tip-row"><span>装备位置</span><span class="val">' + esc(item.etype) + '</span></div>';
  } else if (kind === 'items') {
    h += '<div class="item-tip-row"><span>分类</span><span class="val">' + esc(item.itype) + '</span></div>';
    h += '<div class="item-tip-row"><span>范围</span><span class="val">' + esc(item.scope) + '</span></div>';
    h += '<div class="item-tip-row"><span>消耗</span><span class="val">' + (item.consumable ? '是' : '否') + '</span></div>';
  }
  if (item.price !== undefined) {
    h += '<div class="item-tip-row"><span>价格</span><span class="val">' + item.price + 'G</span></div>';
  }

  if (item.params && item.params.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">能力值</div><div class="item-tip-list">';
    item.params.forEach(p => {
      const sign = p.value > 0 ? '+' : '';
      h += '<div>' + esc(p.name) + ' ' + sign + p.value + '</div>';
    });
    h += '</div></div>';
  }

  if (item.traits && item.traits.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">特性</div><div class="item-tip-list">';
    item.traits.forEach(t => { h += '<div>· ' + esc(t) + '</div>'; });
    h += '</div></div>';
  }

  if (item.effects && item.effects.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">使用效果</div><div class="item-tip-list">';
    item.effects.forEach(e => { h += '<div>· ' + esc(e) + '</div>'; });
    h += '</div></div>';
  }
  return h;
}

function buildTroopTipHtml(ref) {
  if (!ref) return '<div style="color:var(--text2)">未找到条目</div>';
  let h = '<div class="item-tip-title">#' + ref.id + ' ' + esc(ref.name) +
    '<span class="item-tip-kind">[敌群]</span>';
  if (ref.special) h += '<span class="item-tip-badge">剧情</span>';
  h += '</div>';
  if (ref.specialReason) h += '<div class="item-tip-desc">' + esc(ref.specialReason) + '</div>';
  h += '<div class="item-tip-row"><span>类型</span><span class="val">' + esc(ref.methodLabel || '战斗') + '</span></div>';
  h += '<div class="item-tip-row"><span>可逃跑</span><span class="val">' + (ref.canEscape ? '是' : '否') + '</span></div>';
  h += '<div class="item-tip-row"><span>可失败</span><span class="val">' + (ref.canLose ? '是' : '否') + '</span></div>';

  if (ref.enemies && ref.enemies.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">敌群成员</div><div class="item-tip-list">';
    ref.enemies.forEach(e => {
      let line = '<span class="ref-link" data-kind="enemies" data-id="' + e.id + '">' + esc(e.name) + '</span> x' + e.count;
      if (e.hidden) line += ' (隐藏' + e.hidden + ')';
      h += '<div>· ' + line + '</div>';
    });
    h += '</div></div>';
  } else {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">敌群成员</div><div class="item-tip-list">';
    h += '<div style="color:var(--text2)">无成员数据</div></div>';
  }
  return h;
}

function buildEncounterTipHtml(ref) {
  if (!ref) return '<div style="color:var(--text2)">未找到条目</div>';
  let h = '<div class="item-tip-title">' + esc(ref.name || '随机遇敌') +
    '<span class="item-tip-kind">[遇敌]</span>';
  if (ref.special) h += '<span class="item-tip-badge">剧情</span>';
  h += '</div>';
  if (ref.specialReason) h += '<div class="item-tip-desc">' + esc(ref.specialReason) + '</div>';
  if (ref.mapName) {
    h += '<div class="item-tip-row"><span>地图</span><span class="val">' + esc(ref.mapName) + (ref.mapId ? ' (#' + ref.mapId + ')' : '') + '</span></div>';
  }
  if (ref.encounterStep !== undefined && ref.encounterStep !== null) {
    h += '<div class="item-tip-row"><span>遇敌步数</span><span class="val">' + ref.encounterStep + '</span></div>';
  }
  if (ref.canEscape !== undefined) {
    h += '<div class="item-tip-row"><span>可逃跑</span><span class="val">' + (ref.canEscape ? '是' : '否') + '</span></div>';
  }
  if (ref.canLose !== undefined) {
    h += '<div class="item-tip-row"><span>可失败</span><span class="val">' + (ref.canLose ? '是' : '否') + '</span></div>';
  }
  const list = ref.encounters || [];
  h += '<div class="item-tip-section"><div class="item-tip-section-title">可能敌群</div><div class="item-tip-list">';
  if (!list.length) {
    h += '<div style="color:var(--text2)">无遇敌列表</div>';
  } else {
    list.forEach(e => {
      const region = (e.regionSet && e.regionSet.length) ? ('区域 ' + e.regionSet.join(',')) : '全部区域';
      const line = '#' + e.troopId + ' ' + esc(e.troopName) + ' (权重:' + (e.weight || 1) + ' / ' + region + ')';
      h += '<div>· ' + line + '</div>';
      if (e.enemies && e.enemies.length) {
        e.enemies.forEach(en => {
          let s = '<span class="ref-link" data-kind="enemies" data-id="' + en.id + '">' + esc(en.name) + '</span> x' + en.count;
          if (en.hidden) s += ' (隐藏' + en.hidden + ')';
          h += '<div style="margin-left:10px;color:var(--text2)">- ' + s + '</div>';
        });
      }
    });
  }
  h += '</div></div>';
  return h;
}

function buildEnemyTipHtml(enemy) {
  if (!enemy) return '<div style="color:var(--text2)">未找到条目</div>';
  let h = '<div class="item-tip-title">#' + enemy.id + ' ' + esc(enemy.name) +
    '<span class="item-tip-kind">[怪物]</span></div>';
  h += '<div class="item-tip-row"><span>经验值</span><span class="val">' + enemy.exp + '</span></div>';
  h += '<div class="item-tip-row"><span>金币</span><span class="val">' + enemy.gold + '</span></div>';

  if (enemy.params && enemy.params.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">能力值</div><div class="item-tip-list">';
    enemy.params.forEach(p => {
      const sign = p.value > 0 ? '+' : '';
      h += '<div>' + esc(p.name) + ' ' + sign + p.value + '</div>';
    });
    h += '</div></div>';
  }

  if (enemy.traits && enemy.traits.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">特性</div><div class="item-tip-list">';
    enemy.traits.forEach(t => { h += '<div>· ' + esc(t) + '</div>'; });
    h += '</div></div>';
  }

  if (enemy.drops && enemy.drops.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">掉落物</div><div class="item-tip-list">';
    enemy.drops.forEach(d => { h += '<div>· ' + esc(d) + '</div>'; });
    h += '</div></div>';
  }

  if (enemy.actions && enemy.actions.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">行动模式</div><div class="item-tip-list">';
    enemy.actions.forEach(a => { h += '<div>· ' + esc(a.skill) + ' (优先度:' + a.rating + ')</div>'; });
    h += '</div></div>';
  }
  return h;
}

function showTooltip(anchor, html) {
  if (!itemTooltip) return;
  itemTooltip.innerHTML = html;
  itemTooltip.style.display = 'block';
  const rect = anchor.getBoundingClientRect();
  let x = rect.left + window.scrollX;
  let y = rect.bottom + window.scrollY + 6;
  const tipRect = itemTooltip.getBoundingClientRect();
  const maxX = window.scrollX + window.innerWidth - tipRect.width - 8;
  const maxY = window.scrollY + window.innerHeight - tipRect.height - 8;
  if (x > maxX) x = maxX;
  if (y > maxY) y = rect.top + window.scrollY - tipRect.height - 6;
  if (x < window.scrollX + 8) x = window.scrollX + 8;
  if (y < window.scrollY + 8) y = window.scrollY + 8;
  itemTooltip.style.left = x + 'px';
  itemTooltip.style.top = y + 'px';
}

function showItemTooltip(anchor, kind, item) {
  showTooltip(anchor, buildItemTipHtml(kind, item));
}

function showTroopTooltip(anchor, ref) {
  showTooltip(anchor, buildTroopTipHtml(ref));
}

function showEncounterTooltip(anchor, ref) {
  showTooltip(anchor, buildEncounterTipHtml(ref));
}

function showEnemyTooltip(anchor, enemy) {
  showTooltip(anchor, buildEnemyTipHtml(enemy));
}

document.addEventListener('click', async e => {
  const link = e.target.closest('.ref-link');
  if (link) {
    e.preventDefault();
    e.stopPropagation();
    const kind = link.dataset.kind;
    if (kind === 'troop') {
      const payload = link.dataset.ref || '';
      let ref = null;
      try { ref = JSON.parse(decodeURIComponent(payload)); } catch (err) { ref = null; }
      showTroopTooltip(link, ref);
      return;
    }
    if (kind === 'encounter') {
      const payload = link.dataset.ref || '';
      let ref = null;
      try { ref = JSON.parse(decodeURIComponent(payload)); } catch (err) { ref = null; }
      showEncounterTooltip(link, ref);
      return;
    }
    if (kind === 'transfer') {
      const mapId = parseInt(link.dataset.map || '0', 10);
      const x = parseInt(link.dataset.x || '0', 10);
      const y = parseInt(link.dataset.y || '0', 10);
      if (!mapId) return;
      await loadMap(mapId);
      if (!isNaN(x) && !isNaN(y)) focusMapCell(x, y);
      return;
    }
    if (kind === 'enemies') {
      const id = parseInt(link.dataset.id || '0', 10);
      if (!id) return;
      await ensureEncData();
      const enemy = findEncItem('enemies', id);
      showEnemyTooltip(link, enemy);
      return;
    }
    const id = parseInt(link.dataset.id || '0', 10);
    if (!kind || !id) return;
    await ensureEncData();
    const item = findEncItem(kind, id);
    showItemTooltip(link, kind, item);
    return;
  }
  if (!e.target.closest('#itemTooltip')) hideItemTooltip();
});

document.getElementById('detailContent').addEventListener('scroll', hideItemTooltip);
window.addEventListener('resize', hideItemTooltip);

// ===== 事件详情 =====
function showEventDetail(evt) {
  const dc = document.getElementById('detailContent');
  let html = '<div class="info-block"><h3>事件详情</h3>';
  html += infoRow('ID', evt.id);
  html += infoRow('名称', evt.name || '(无名)');
  html += infoRow('坐标', '(' + evt.x + ', ' + evt.y + ')');
  html += infoRow('页数', evt.pageCount);
  html += '</div>';

  // 事件页标签
  if (evt.pages.length > 1) {
    html += '<div class="page-tabs">';
    evt.pages.forEach((pg, i) => {
      html += '<div class="page-tab' + (i===0?' active':'') +
        '" onclick="switchPage(this,' + i + ')">' + pg.index + '</div>';
    });
    html += '</div>';
  }

  // 各页内容
  evt.pages.forEach((pg, i) => {
    html += '<div class="page-content" data-page="' + i + '"' +
      (i > 0 ? ' style="display:none"' : '') + '>';
    html += renderPage(pg);
    html += '</div>';
  });

  pushDetail(html);
}

function switchPage(el, idx) {
  el.parentElement.querySelectorAll('.page-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.querySelectorAll('.page-content').forEach(p => {
    p.style.display = p.dataset.page == idx ? '' : 'none';
  });
}

function renderPage(pg) {
  let h = '<div class="info-block">';
  h += '<h3>事件页 ' + pg.index + '</h3>';
  h += infoRow('触发', pg.trigger);
  if (pg.conditions.length > 0) {
    h += '<div style="margin-top:4px;color:var(--orange);font-size:12px">';
    h += '<b>出现条件:</b><br>';
    pg.conditions.forEach(c => { h += '  ' + esc(c) + '<br>'; });
    h += '</div>';
  }
  h += '</div>';

  // 指令列表
  if (pg.commands.length > 0) {
    h += '<div class="info-block"><h3>指令内容</h3>';
    pg.commands.forEach(cmd => {
      const pad = cmd.indent * 16;
      if (cmd.cls === 'cmd-common-event') {
        const m = cmd.text.match(/#(\d+)/);
        const ceId = m ? m[1] : '0';
        h += '<div class="cmd-line ' + cmd.cls + '" style="padding-left:' + pad + 'px" onclick="loadCommonEvent(' + ceId + ')">';
      } else {
        h += '<div class="cmd-line ' + (cmd.cls||'') + '" style="padding-left:' + pad + 'px">';
      }
      h += renderCmdText(cmd);
      h += '</div>';
    });
    h += '</div>';
  }
  return h;
}

// ===== 公共事件详情 =====
async function loadCommonEvent(ceId) {
  const dc = document.getElementById('detailContent');
  dc.innerHTML = '<div class="empty-state"><div>加载公共事件...</div></div>';
  const res = await fetch('/api/common_event/' + ceId);
  const ce = await res.json();
  if (ce.error) {
    dc.innerHTML = '<div class="empty-state"><div>' + esc(ce.error) + '</div></div>';
    return;
  }
  let html = '<div class="info-block"><h3>公共事件详情</h3>';
  html += infoRow('ID', ce.id);
  html += infoRow('名称', ce.name || '(无名)');
  html += infoRow('触发', ce.trigger);
  if (ce.switchId) html += infoRow('条件开关', ce.switchName + ' (#' + ce.switchId + ')');
  html += '</div>';
  if (ce.commands && ce.commands.length > 0) {
    html += '<div class="info-block"><h3>指令内容</h3>';
    ce.commands.forEach(function(cmd) {
      const pad = cmd.indent * 16;
      if (cmd.cls === 'cmd-common-event') {
        const m = cmd.text.match(/#(\d+)/);
        const cid = m ? m[1] : '0';
        html += '<div class="cmd-line ' + cmd.cls + '" style="padding-left:' + pad + 'px" onclick="loadCommonEvent(' + cid + ')">';
      } else {
        html += '<div class="cmd-line ' + (cmd.cls||'') + '" style="padding-left:' + pad + 'px">';
      }
      html += renderCmdText(cmd) + '</div>';
    });
    html += '</div>';
  }
  pushDetail(html);
}

// ===== 全局搜索 =====
const gsInput = document.getElementById('globalSearchInput');
const gsBtn = document.getElementById('globalSearchBtn');

async function globalSearch() {
  const kw = gsInput.value.trim();
  if (!kw) return;
  const dc = document.getElementById('detailContent');
  dc.innerHTML = '<div class="empty-state"><div>搜索中，请稍候...</div></div>';
  document.getElementById('statusBar').textContent = '正在搜索: ' + kw;
  const res = await fetch('/api/search?q=' + encodeURIComponent(kw));
  const data = await res.json();
  document.getElementById('statusBar').textContent = '搜索完成 — 找到 ' + data.length + ' 个结果';
  renderSearchResults(data, kw);
}

function renderSearchResults(data, kw) {
  const dc = document.getElementById('detailContent');
  if (data.length === 0) {
    pushDetail('<div class="empty-state"><div>未找到匹配结果</div></div>');
    return;
  }
  const TC = {treasure:'#ffd43b',transfer:'#74b9ff',battle:'#ff6b6b',dialog:'#51cf66',other:'#636e72'};
  const TL = {treasure:'宝箱',transfer:'传送',battle:'战斗',dialog:'对话',other:'其他'};
  let html = '<div class="info-block"><h3>搜索结果: "' + esc(kw) + '" (' + data.length + ' 条)</h3></div>';
  data.forEach((r, i) => {
    const tc = TC[r.type] || TC.other;
    const tl = TL[r.type] || '其他';
    html += '<div class="search-result" onclick="gotoResult('+i+')">';
    html += '<div class="sr-header">';
    html += '<span class="dot" style="background:'+tc+'"></span>';
    html += '<span class="sr-map">' + esc(r.mapName) + '</span>';
    html += '<span class="sr-evt">' + esc(r.eventName||'(无名)') + ' <span style="color:'+tc+'">['+tl+']</span></span>';
    html += '<span class="sr-pos">(' + r.x + ',' + r.y + ')</span>';
    html += '</div>';
    html += '<div class="sr-match">';
    r.matches.forEach(m => { html += esc(m) + '<br>'; });
    html += '</div></div>';
  });
  pushDetail(html);
  window._searchResults = data;
}

async function gotoResult(idx) {
  const r = window._searchResults[idx];
  if (!r) return;
  await loadMap(r.mapId);
  const evt = mapData.events.find(e => e.id === r.eventId);
  if (evt) showEventDetail(evt);
}

gsBtn.addEventListener('click', globalSearch);
gsInput.addEventListener('keydown', e => { if (e.key === 'Enter') globalSearch(); });

// ===== 图鉴 =====
let encData = null;
let encTab = 'weapons';
let encSelIdx = -1;

function toggleEncyclopedia() {
  const p = document.getElementById('encPanel');
  const m = document.querySelector('.main');
  if (p.style.display === 'none') {
    p.style.display = 'flex';
    m.style.display = 'none';
    if (!encData) loadEncyclopedia();
  } else {
    p.style.display = 'none';
    m.style.display = 'flex';
  }
}

function switchEncTab(tab) {
  encTab = tab;
  encSelIdx = -1;
  document.querySelectorAll('.enc-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.getElementById('encDetail').innerHTML = '<div style="color:var(--muted)">点击左侧条目查看详情</div>';
  document.getElementById('encSearch').value = '';
  renderEncList();
}

async function loadEncyclopedia() {
  document.getElementById('encList').innerHTML = '<div style="padding:20px;color:var(--muted)">加载中...</div>';
  await ensureEncData();
  renderEncList();
}

function filterEnc() { renderEncList(); }

function renderEncList() {
  if (!encData) return;
  const list = encData[encTab] || [];
  const q = document.getElementById('encSearch').value.toLowerCase();
  const filtered = q ? list.filter(x => x.name.toLowerCase().includes(q)) : list;
  const el = document.getElementById('encList');
  let html = '';
  filtered.forEach((item, i) => {
    const origIdx = list.indexOf(item);
    let right = '';
    if (encTab === 'enemies') {
      right = item.exp ? `<span class="price">EXP:${item.exp} G:${item.gold}</span>` : '';
    } else {
      right = item.price ? `<span class="price">${item.price}G</span>` : '';
    }
    html += `<div class="enc-item${origIdx===encSelIdx?' sel':''}" onclick="showEncDetail(${origIdx})">
      <span><span class="eid">#${item.id}</span> ${esc(item.name)}</span>${right}</div>`;
  });
  el.innerHTML = html || '<div style="padding:20px;color:var(--muted)">无结果</div>';
}

function showEncDetail(idx) {
  encSelIdx = idx;
  renderEncList();
  const item = (encData[encTab] || [])[idx];
  if (!item) return;
  const el = document.getElementById('encDetail');
  let h = `<div class="enc-detail"><h3>#${item.id} ${esc(item.name)}</h3>`;

  // 描述
  if (item.desc) h += `<div class="desc">${esc(item.desc)}</div>`;

  // 类型/价格行
  if (encTab === 'weapons') {
    h += `<div class="stat"><span>类型</span><span class="val">${esc(item.wtype)}</span></div>`;
  } else if (encTab === 'armors') {
    h += `<div class="stat"><span>防具类型</span><span class="val">${esc(item.atype)}</span></div>`;
    h += `<div class="stat"><span>装备位置</span><span class="val">${esc(item.etype)}</span></div>`;
  } else if (encTab === 'items') {
    h += `<div class="stat"><span>分类</span><span class="val">${esc(item.itype)}</span></div>`;
    h += `<div class="stat"><span>范围</span><span class="val">${esc(item.scope)}</span></div>`;
    h += `<div class="stat"><span>消耗</span><span class="val">${item.consumable ? '是' : '否'}</span></div>`;
  } else if (encTab === 'enemies') {
    h += `<div class="stat"><span>经验值</span><span class="val">${item.exp}</span></div>`;
    h += `<div class="stat"><span>金币</span><span class="val">${item.gold}</span></div>`;
  }
  if (item.price !== undefined && encTab !== 'enemies') {
    h += `<div class="stat"><span>价格</span><span class="val">${item.price}G</span></div>`;
  }

  // 能力值
  if (item.params && item.params.length) {
    h += `<div class="section"><div class="section-title">能力值</div>`;
    item.params.forEach(p => {
      const color = p.value > 0 ? '#51cf66' : '#ff6b6b';
      h += `<div class="stat"><span>${esc(p.name)}</span><span class="val" style="color:${color}">${p.value > 0 ? '+' : ''}${p.value}</span></div>`;
    });
    h += `</div>`;
  }

  // 特性
  if (item.traits && item.traits.length) {
    h += `<div class="section"><div class="section-title">特性</div>`;
    item.traits.forEach(t => { h += `<div class="trait">· ${esc(t)}</div>`; });
    h += `</div>`;
  }

  // 物品效果
  if (item.effects && item.effects.length) {
    h += `<div class="section"><div class="section-title">使用效果</div>`;
    item.effects.forEach(e => { h += `<div class="trait">· ${esc(e)}</div>`; });
    h += `</div>`;
  }

  // 怪物掉落
  if (item.drops && item.drops.length) {
    h += `<div class="section"><div class="section-title">掉落物</div>`;
    item.drops.forEach(d => { h += `<div class="trait">· ${esc(d)}</div>`; });
    h += `</div>`;
  }

  // 怪物行动
  if (item.actions && item.actions.length) {
    h += `<div class="section"><div class="section-title">行动模式</div>`;
    item.actions.forEach(a => {
      h += `<div class="trait">· ${esc(a.skill)} (优先度:${a.rating})</div>`;
    });
    h += `</div>`;
  }

  h += `</div>`;
  el.innerHTML = h;
}

// ===== 初始化 =====
loadTree();
</script>
</body>
</html>
"""


# ============================================================
# 第5部分：程序入口
# ============================================================

def main():
    global db, interpreter

    # 检查关键文件
    if not os.path.exists(os.path.join(DATA_DIR, "MapInfos.json")):
        print(f"[错误] 在 {DATA_DIR} 下未找到 MapInfos.json")
        print("请将本脚本放在包含 RPG Maker MV 数据文件的目录中运行。")
        input("按回车键退出...")
        return

    # 初始化数据库和解析器
    print("正在加载数据库...")
    db = DatabaseManager()
    interpreter = EventInterpreter(db)
    print(f"  物品: {len(db.items)} | 武器: {len(db.weapons)} | 防具: {len(db.armors)}")
    print(f"  开关: {len(db.switches)} | 变量: {len(db.variables)}")
    ce_count = sum(1 for c in db.common_events if c and isinstance(c, dict))
    ts_count = sum(1 for t in db.tilesets if t and isinstance(t, dict))
    print(f"  公共事件: {ce_count} | 图块集: {ts_count}")

    # 启动 HTTP 服务器
    server = HTTPServer(("127.0.0.1", PORT), RequestHandler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n服务器已启动: {url}")
    print("按 Ctrl+C 停止服务器\n")

    # 在浏览器中打开
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止。")
        server.server_close()


if __name__ == "__main__":
    main()
