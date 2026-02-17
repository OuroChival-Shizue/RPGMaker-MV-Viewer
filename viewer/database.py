"""Database cache and helper mappings for RPGMV JSON data."""

from __future__ import annotations

from .data_loader import DataLoader


def build_name_map(json_data, fallback: str = "未知"):
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


def build_switch_var_map(json_array, fallback_prefix: str = ""):
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
    """Loads and caches common database mappings for one game."""

    def __init__(self, loader: DataLoader):
        self.loader = loader
        self.engine = loader.engine

        self.raw_items = loader.load_json("Items.json") or []
        self.raw_weapons = loader.load_json("Weapons.json") or []
        self.raw_armors = loader.load_json("Armors.json") or []
        self.raw_enemies = loader.load_json("Enemies.json") or []
        self.raw_skills = loader.load_json("Skills.json") or []
        self.raw_states = loader.load_json("States.json") or []
        self.raw_troops = loader.load_json("Troops.json") or []

        self.item_types = {}
        for item in self.raw_items:
            if item is not None and isinstance(item, dict):
                iid = item.get("id")
                if iid is not None:
                    self.item_types[iid] = item.get("itypeId", 1)

        self.items = build_name_map(self.raw_items, "未知物品")
        self.weapons = build_name_map(self.raw_weapons, "未知武器")
        self.armors = build_name_map(self.raw_armors, "未知防具")
        self.enemies = build_name_map(self.raw_enemies, "未知敌人")
        self.skills = build_name_map(self.raw_skills, "技能")
        self.states = build_name_map(self.raw_states, "状态")
        self.troops = build_name_map(self.raw_troops, "敌群")

        system_data = loader.load_json("System.json")
        if system_data:
            self.switches = build_switch_var_map(system_data.get("switches", []), "开关")
            self.variables = build_switch_var_map(system_data.get("variables", []), "变量")
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

        self.map_infos = loader.load_json("MapInfos.json") or []
        self.common_events = loader.load_json("CommonEvents.json") or []
        self.common_event_names = build_name_map(self.common_events, "公共事件")
        self.tilesets = loader.load_json("Tilesets.json") or []

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

    def get_tileset(self, tileset_id):
        if not isinstance(self.tilesets, list):
            return None
        for ts in self.tilesets:
            if ts and isinstance(ts, dict) and ts.get("id") == tileset_id:
                return ts
        return None

    def get_tileset_flags(self, tileset_id):
        ts = self.get_tileset(tileset_id)
        if ts and isinstance(ts, dict):
            flags = ts.get("flags", [])
            if isinstance(flags, list):
                return flags
        return []

    def get_tileset_names(self, tileset_id):
        ts = self.get_tileset(tileset_id)
        if ts and isinstance(ts, dict):
            names = ts.get("tilesetNames", [])
            if isinstance(names, list) and names:
                return names
            # VX 旧版兼容: 由 autotiles + tilesetName 组装到 MV 9 槽位。
            tileset_name = str(ts.get("tilesetName", "") or "").strip()
            autotiles = ts.get("autotileNames", [])
            if isinstance(autotiles, list) or tileset_name:
                out = [""] * 9
                if isinstance(autotiles, list):
                    for idx, name in enumerate(autotiles[:5]):
                        out[idx] = str(name or "").strip()
                if tileset_name:
                    out[5] = tileset_name
                return out
        return []

    def get_map_tree(self):
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
            children_map[pid].sort(key=lambda x: info_dict.get(x, {}).get("order", 0))

        def build_tree(parent_id):
            nodes = []
            for cid in children_map.get(parent_id, []):
                info = info_dict.get(cid, {})
                nodes.append({
                    "id": cid,
                    "name": info.get("name", f"地图#{cid}"),
                    "children": build_tree(cid),
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
