"""Adapters that normalize RPG Maker VX/VX Ace data into MV-like structures."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from ._vendor.rubymarshal.classes import RubyObject, RubyString, Symbol, UserDef


def _decode_bytes(raw: bytes) -> str:
    for enc in ("utf-8", "cp932", "shift_jis", "latin1"):
        try:
            return raw.decode(enc)
        except Exception:  # noqa: BLE001
            continue
    return raw.decode("utf-8", errors="replace")


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def _to_bool(value: Any) -> bool:
    return bool(value)


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return _decode_bytes(value)
    if isinstance(value, RubyString):
        return str(value)
    if value is None:
        return ""
    return str(value)


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, RubyObject):
        return obj.attributes.get(name, default)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default


def _first_attr(obj: Any, names: list[str], default: Any = None) -> Any:
    for name in names:
        value = _attr(obj, name, None)
        if value is not None:
            return value
    return default


def _decode_table(private_data: bytes) -> list[int]:
    if len(private_data) < 20:
        return []
    _, _, _, _, size = struct.unpack_from("<IIIII", private_data, 0)
    if size <= 0:
        return []
    if len(private_data) < 20 + (size * 2):
        size = max((len(private_data) - 20) // 2, 0)
    if size <= 0:
        return []
    vals = struct.unpack_from(f"<{size}h", private_data, 20)
    return [int(v) for v in vals]


def _to_plain(value: Any) -> Any:
    if isinstance(value, bytes):
        return _decode_bytes(value)
    if isinstance(value, RubyString):
        return str(value)
    if isinstance(value, Symbol):
        return value.name
    if isinstance(value, UserDef):
        if value.ruby_class_name == "Table":
            return _decode_table(value._private_data or b"")
        return None
    if isinstance(value, RubyObject):
        out: dict[str, Any] = {}
        for key, val in value.attributes.items():
            name = str(key)
            if name.startswith("@"):
                name = name[1:]
            out[name] = _to_plain(val)
        return out
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            key = _to_plain(k)
            out[key] = _to_plain(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    return value


def _convert_command_list(raw_list: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw_list, list):
        return out
    for cmd in raw_list:
        if not isinstance(cmd, (RubyObject, dict)):
            continue
        out.append(
            {
                "code": _to_int(_first_attr(cmd, ["@code", "code"], 0)),
                "indent": _to_int(_first_attr(cmd, ["@indent", "indent"], 0)),
                "parameters": _to_plain(_first_attr(cmd, ["@parameters", "parameters"], [])) or [],
            }
        )
    return out


def _convert_condition(raw_cond: Any) -> dict[str, Any]:
    return {
        "switch1Valid": _to_bool(_first_attr(raw_cond, ["@switch1_valid", "switch1Valid"], False)),
        "switch2Valid": _to_bool(_first_attr(raw_cond, ["@switch2_valid", "switch2Valid"], False)),
        "variableValid": _to_bool(_first_attr(raw_cond, ["@variable_valid", "variableValid"], False)),
        "selfSwitchValid": _to_bool(_first_attr(raw_cond, ["@self_switch_valid", "selfSwitchValid"], False)),
        "itemValid": _to_bool(_first_attr(raw_cond, ["@item_valid", "itemValid"], False)),
        "actorValid": _to_bool(_first_attr(raw_cond, ["@actor_valid", "actorValid"], False)),
        "switch1Id": _to_int(_first_attr(raw_cond, ["@switch1_id", "switch1Id"], 0)),
        "switch2Id": _to_int(_first_attr(raw_cond, ["@switch2_id", "switch2Id"], 0)),
        "variableId": _to_int(_first_attr(raw_cond, ["@variable_id", "variableId"], 0)),
        "variableValue": _to_int(_first_attr(raw_cond, ["@variable_value", "variableValue"], 0)),
        "selfSwitchCh": _as_text(_first_attr(raw_cond, ["@self_switch_ch", "selfSwitchCh"], "A")),
        "itemId": _to_int(_first_attr(raw_cond, ["@item_id", "itemId"], 0)),
        "actorId": _to_int(_first_attr(raw_cond, ["@actor_id", "actorId"], 0)),
    }


def _convert_page_image(raw_page: Any) -> dict[str, Any]:
    graphic = _first_attr(raw_page, ["@graphic", "graphic"], None)
    character_name = _as_text(_first_attr(graphic, ["@character_name", "character_name", "characterName"], ""))
    return {
        "tileId": _to_int(_first_attr(graphic, ["@tile_id", "tile_id", "tileId"], 0)),
        "characterName": character_name,
        "characterIndex": _to_int(_first_attr(graphic, ["@character_index", "character_index", "characterIndex"], 0)),
        "direction": _to_int(_first_attr(graphic, ["@direction", "direction"], 2), 2),
        "pattern": _to_int(_first_attr(graphic, ["@pattern", "pattern"], 0), 0),
        "isBigCharacter": character_name.startswith("$"),
        "faceName": "",
        "faceIndex": 0,
    }


def _convert_page(raw_page: Any) -> dict[str, Any]:
    return {
        "trigger": _to_int(_first_attr(raw_page, ["@trigger", "trigger"], 0)),
        "conditions": _convert_condition(_first_attr(raw_page, ["@condition", "conditions"], {})),
        "image": _convert_page_image(raw_page),
        "list": _convert_command_list(_first_attr(raw_page, ["@list", "list"], [])),
    }


def _convert_event(raw_evt: Any) -> dict[str, Any]:
    pages_raw = _first_attr(raw_evt, ["@pages", "pages"], [])
    pages: list[dict[str, Any]] = []
    if isinstance(pages_raw, list):
        for raw_page in pages_raw:
            if raw_page is None:
                continue
            pages.append(_convert_page(raw_page))
    return {
        "id": _to_int(_first_attr(raw_evt, ["@id", "id"], 0)),
        "name": _as_text(_first_attr(raw_evt, ["@name", "name"], "")),
        "x": _to_int(_first_attr(raw_evt, ["@x", "x"], 0)),
        "y": _to_int(_first_attr(raw_evt, ["@y", "y"], 0)),
        "pages": pages,
    }


def _convert_event_dict_to_list(raw_events: Any) -> list[Any]:
    if not isinstance(raw_events, dict):
        return []
    max_id = 0
    parsed: dict[int, dict[str, Any]] = {}
    for key, value in raw_events.items():
        evt = _convert_event(value)
        evt_id = _to_int(key, _to_int(evt.get("id", 0)))
        evt["id"] = evt_id
        if evt_id <= 0:
            continue
        parsed[evt_id] = evt
        max_id = max(max_id, evt_id)
    out = [None] * (max_id + 1)
    for evt_id, evt in parsed.items():
        out[evt_id] = evt
    return out


def _base_entry(item: Any, idx: int) -> dict[str, Any]:
    return {
        "id": _to_int(_first_attr(item, ["@id", "id"], idx)),
        "name": _as_text(_first_attr(item, ["@name", "name"], "")),
        "description": _as_text(_first_attr(item, ["@description", "description"], "")),
        "iconIndex": _to_int(_first_attr(item, ["@icon_index", "icon_index", "iconIndex"], 0)),
        "note": _as_text(_first_attr(item, ["@note", "note"], "")),
    }


def _extract_params(item: Any) -> list[int]:
    raw = _to_plain(_first_attr(item, ["@params", "params"], None))
    if isinstance(raw, list) and raw:
        vals = [_to_int(v, 0) for v in raw]
        if len(vals) < 8:
            vals.extend([0] * (8 - len(vals)))
        return vals[:8]

    fallback = [
        _to_int(_first_attr(item, ["@maxhp", "maxhp", "@mhp", "mhp"], 0)),
        _to_int(_first_attr(item, ["@maxsp", "maxsp", "@maxmp", "maxmp", "@mmp", "mmp"], 0)),
        _to_int(_first_attr(item, ["@atk", "atk", "@str", "str"], 0)),
        _to_int(_first_attr(item, ["@def", "def", "@vit", "vit"], 0)),
        _to_int(_first_attr(item, ["@mat", "mat", "@spi", "spi", "@int", "int"], 0)),
        _to_int(_first_attr(item, ["@mdf", "mdf"], 0)),
        _to_int(_first_attr(item, ["@agi", "agi", "@dex", "dex"], 0)),
        _to_int(_first_attr(item, ["@luk", "luk"], 0)),
    ]
    return fallback


def _convert_traits(item: Any) -> list[dict[str, Any]]:
    traits_raw = _first_attr(item, ["@features", "features", "@traits", "traits"], [])
    if not isinstance(traits_raw, list):
        return []
    traits: list[dict[str, Any]] = []
    for t in traits_raw:
        if not isinstance(t, (RubyObject, dict)):
            continue
        traits.append(
            {
                "code": _to_int(_first_attr(t, ["@code", "code"], 0)),
                "dataId": _to_int(_first_attr(t, ["@data_id", "data_id", "@dataId", "dataId"], 0)),
                "value": _to_float(_first_attr(t, ["@value", "value"], 0), 0),
            }
        )
    return traits


def _convert_effects(item: Any) -> list[dict[str, Any]]:
    effects_raw = _first_attr(item, ["@effects", "effects"], [])
    if not isinstance(effects_raw, list):
        return []
    out: list[dict[str, Any]] = []
    for e in effects_raw:
        if not isinstance(e, (RubyObject, dict)):
            continue
        out.append(
            {
                "code": _to_int(_first_attr(e, ["@code", "code"], 0)),
                "dataId": _to_int(_first_attr(e, ["@data_id", "data_id", "@dataId", "dataId"], 0)),
                "value1": _to_float(_first_attr(e, ["@value1", "value1"], 0), 0),
                "value2": _to_float(_first_attr(e, ["@value2", "value2"], 0), 0),
            }
        )
    return out


def _convert_named_list(raw: Any, extra_builder=None) -> list[Any]:
    if not isinstance(raw, list):
        return []
    out: list[Any] = [None] * len(raw)
    for idx, item in enumerate(raw):
        if item is None:
            out[idx] = None
            continue
        if not isinstance(item, (RubyObject, dict)):
            out[idx] = _to_plain(item)
            continue
        entry = _base_entry(item, idx)
        if extra_builder:
            entry.update(extra_builder(item))
        out[idx] = entry
    return out


def _convert_map_infos(raw: Any) -> list[Any]:
    if not isinstance(raw, dict):
        return []
    max_id = 0
    parsed: dict[int, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(value, (RubyObject, dict)):
            continue
        map_id = _to_int(key, 0)
        if map_id <= 0:
            continue
        parsed[map_id] = {
            "id": map_id,
            "name": _as_text(_first_attr(value, ["@name", "name"], f"地图#{map_id}")),
            "parentId": _to_int(_first_attr(value, ["@parent_id", "parent_id", "@parentId", "parentId"], 0)),
            "order": _to_int(_first_attr(value, ["@order", "order"], 0)),
        }
        max_id = max(max_id, map_id)
    out = [None] * (max_id + 1)
    for map_id, info in parsed.items():
        out[map_id] = info
    return out


def _convert_common_events(raw: Any) -> list[Any]:
    def build_extra(item: Any) -> dict[str, Any]:
        return {
            "trigger": _to_int(_first_attr(item, ["@trigger", "trigger"], 0)),
            "switchId": _to_int(_first_attr(item, ["@switch_id", "switch_id", "@switchId", "switchId"], 0)),
            "list": _convert_command_list(_first_attr(item, ["@list", "list"], [])),
        }

    return _convert_named_list(raw, extra_builder=build_extra)


def _convert_troops(raw: Any) -> list[Any]:
    def build_extra(item: Any) -> dict[str, Any]:
        members_raw = _first_attr(item, ["@members", "members"], [])
        members: list[dict[str, Any]] = []
        if isinstance(members_raw, list):
            for m in members_raw:
                if not isinstance(m, (RubyObject, dict)):
                    continue
                members.append(
                    {
                        "enemyId": _to_int(_first_attr(m, ["@enemy_id", "enemy_id", "@enemyId", "enemyId"], 0)),
                        "hidden": _to_bool(_first_attr(m, ["@hidden", "hidden"], False)),
                    }
                )
        return {"members": members}

    return _convert_named_list(raw, extra_builder=build_extra)


def _default_equip_types() -> list[str]:
    return ["", "武器", "盾牌", "头部", "身体", "饰品"]


def _normalize_named_array(value: Any) -> list[Any]:
    arr = _to_plain(value)
    if isinstance(arr, list):
        return arr
    return []


def _convert_system(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, (RubyObject, dict)):
        return {}
    equip_types = _normalize_named_array(_first_attr(raw, ["@equip_types", "equip_types", "@equipTypes", "equipTypes"], []))
    if not equip_types:
        equip_types = _default_equip_types()
    return {
        "gameTitle": _as_text(_first_attr(raw, ["@game_title", "game_title", "@gameTitle", "gameTitle"], "")),
        "switches": _normalize_named_array(_first_attr(raw, ["@switches", "switches"], [])),
        "variables": _normalize_named_array(_first_attr(raw, ["@variables", "variables"], [])),
        "elements": _normalize_named_array(_first_attr(raw, ["@elements", "elements"], [])),
        "weaponTypes": _normalize_named_array(_first_attr(raw, ["@weapon_types", "weapon_types", "@weaponTypes", "weaponTypes"], [])),
        "armorTypes": _normalize_named_array(_first_attr(raw, ["@armor_types", "armor_types", "@armorTypes", "armorTypes"], [])),
        "equipTypes": equip_types,
        "skillTypes": _normalize_named_array(_first_attr(raw, ["@skill_types", "skill_types", "@skillTypes", "skillTypes"], [])),
    }


def _convert_items(raw: Any) -> list[Any]:
    def build_extra(item: Any) -> dict[str, Any]:
        kind_raw = _to_int(_first_attr(item, ["@kind", "kind"], 0), 0)
        itype_id = _to_int(_first_attr(item, ["@itype_id", "itype_id", "@itypeId", "itypeId"], 0), 0)
        if itype_id <= 0:
            # VX 常见 kind: 0 普通, 1 关键。对齐 MV: 1 普通, 2 关键。
            itype_id = 2 if kind_raw == 1 else 1
        return {
            "price": _to_int(_first_attr(item, ["@price", "price"], 0)),
            "itypeId": itype_id,
            "consumable": _to_bool(_first_attr(item, ["@consumable", "consumable"], True)),
            "scope": _to_int(_first_attr(item, ["@scope", "scope"], 0)),
            "effects": _convert_effects(item),
            "params": _extract_params(item),
            "traits": _convert_traits(item),
        }

    return _convert_named_list(raw, extra_builder=build_extra)


def _convert_weapons(raw: Any) -> list[Any]:
    def build_extra(item: Any) -> dict[str, Any]:
        return {
            "price": _to_int(_first_attr(item, ["@price", "price"], 0)),
            "wtypeId": _to_int(_first_attr(item, ["@wtype_id", "wtype_id", "@wtypeId", "wtypeId"], 0)),
            "etypeId": _to_int(_first_attr(item, ["@etype_id", "etype_id", "@etypeId", "etypeId"], 1), 1),
            "params": _extract_params(item),
            "traits": _convert_traits(item),
        }

    return _convert_named_list(raw, extra_builder=build_extra)


def _convert_armors(raw: Any) -> list[Any]:
    def build_extra(item: Any) -> dict[str, Any]:
        return {
            "price": _to_int(_first_attr(item, ["@price", "price"], 0)),
            "atypeId": _to_int(_first_attr(item, ["@atype_id", "atype_id", "@atypeId", "atypeId"], 0)),
            "etypeId": _to_int(_first_attr(item, ["@etype_id", "etype_id", "@etypeId", "etypeId"], 2), 2),
            "params": _extract_params(item),
            "traits": _convert_traits(item),
        }

    return _convert_named_list(raw, extra_builder=build_extra)


def _convert_drop_item(drop: Any) -> dict[str, Any]:
    return {
        "kind": _to_int(_first_attr(drop, ["@kind", "kind"], 0)),
        "dataId": _to_int(_first_attr(drop, ["@data_id", "data_id", "@dataId", "dataId"], 0)),
        "denominator": max(1, _to_int(_first_attr(drop, ["@denominator", "denominator"], 1), 1)),
    }


def _convert_enemy_actions(item: Any) -> list[dict[str, Any]]:
    actions_raw = _first_attr(item, ["@actions", "actions"], [])
    if not isinstance(actions_raw, list):
        return []
    out: list[dict[str, Any]] = []
    for act in actions_raw:
        if not isinstance(act, (RubyObject, dict)):
            continue
        out.append(
            {
                "skillId": _to_int(_first_attr(act, ["@skill_id", "skill_id", "@skillId", "skillId"], 0)),
                "rating": _to_int(_first_attr(act, ["@rating", "rating"], 5), 5),
                "conditionType": _to_int(_first_attr(act, ["@condition_type", "condition_type"], 0)),
                "conditionParam1": _to_float(_first_attr(act, ["@condition_param1", "condition_param1"], 0), 0),
                "conditionParam2": _to_float(_first_attr(act, ["@condition_param2", "condition_param2"], 0), 0),
            }
        )
    return out


def _convert_enemy_drop_items(item: Any) -> list[dict[str, Any]]:
    drops_raw = _first_attr(item, ["@drop_items", "drop_items", "@dropItems", "dropItems"], None)
    out: list[dict[str, Any]] = []
    if isinstance(drops_raw, list):
        for d in drops_raw:
            if not isinstance(d, (RubyObject, dict)):
                continue
            out.append(_convert_drop_item(d))
    # VX 旧字段回退
    for key in ("@drop_item1", "drop_item1", "@drop_item2", "drop_item2"):
        drop = _attr(item, key, None)
        if isinstance(drop, (RubyObject, dict)):
            out.append(_convert_drop_item(drop))
    return out


def _convert_enemies(raw: Any) -> list[Any]:
    def build_extra(item: Any) -> dict[str, Any]:
        return {
            "params": _extract_params(item),
            "exp": _to_int(_first_attr(item, ["@exp", "exp"], 0)),
            "gold": _to_int(_first_attr(item, ["@gold", "gold"], 0)),
            "battlerName": _as_text(_first_attr(item, ["@battler_name", "battler_name", "@battlerName", "battlerName"], "")),
            "battlerHue": _to_int(_first_attr(item, ["@battler_hue", "battler_hue", "@battlerHue", "battlerHue"], 0)),
            "dropItems": _convert_enemy_drop_items(item),
            "actions": _convert_enemy_actions(item),
            "traits": _convert_traits(item),
        }

    return _convert_named_list(raw, extra_builder=build_extra)


def _convert_skills(raw: Any) -> list[Any]:
    def build_damage(item: Any) -> dict[str, Any]:
        dmg = _first_attr(item, ["@damage", "damage"], None)
        if isinstance(dmg, (RubyObject, dict)):
            return {
                "type": _to_int(_first_attr(dmg, ["@type", "type"], 0)),
                "elementId": _to_int(_first_attr(dmg, ["@element_id", "element_id", "@elementId", "elementId"], 0)),
                "formula": _as_text(_first_attr(dmg, ["@formula", "formula"], "")),
                "variance": _to_int(_first_attr(dmg, ["@variance", "variance"], 0)),
                "critical": _to_bool(_first_attr(dmg, ["@critical", "critical"], False)),
            }
        return {}

    def build_legacy_damage(item: Any) -> dict[str, Any]:
        return {
            "baseDamage": _to_int(_first_attr(item, ["@base_damage", "base_damage", "@baseDamage", "baseDamage"], 0)),
            "atkF": _to_int(_first_attr(item, ["@atk_f", "atk_f", "@atkF", "atkF"], 0)),
            "spiF": _to_int(_first_attr(item, ["@spi_f", "spi_f", "@mat_f", "mat_f", "@spiF", "spiF"], 0)),
            "variance": _to_int(_first_attr(item, ["@variance", "variance"], 0)),
            "elementSet": _to_plain(_first_attr(item, ["@element_set", "element_set", "@elementSet", "elementSet"], [])) or [],
        }

    def build_extra(item: Any) -> dict[str, Any]:
        damage = build_damage(item)
        return {
            "stypeId": _to_int(_first_attr(item, ["@stype_id", "stype_id", "@stypeId", "stypeId"], 0)),
            "scope": _to_int(_first_attr(item, ["@scope", "scope"], 0)),
            "mpCost": _to_int(_first_attr(item, ["@mp_cost", "mp_cost", "@mpCost", "mpCost"], 0)),
            "tpCost": _to_int(_first_attr(item, ["@tp_cost", "tp_cost", "@tpCost", "tpCost"], 0)),
            "tpGain": _to_int(_first_attr(item, ["@tp_gain", "tp_gain", "@tpGain", "tpGain"], 0)),
            "speed": _to_int(_first_attr(item, ["@speed", "speed"], 0)),
            "repeats": _to_int(_first_attr(item, ["@repeats", "repeats"], 1), 1),
            "successRate": _to_int(_first_attr(item, ["@success_rate", "success_rate", "@successRate", "successRate", "@hit", "hit"], 100), 100),
            "hitType": _to_int(_first_attr(item, ["@hit_type", "hit_type", "@hitType", "hitType"], 0)),
            "occasion": _to_int(_first_attr(item, ["@occasion", "occasion"], 0)),
            "damage": damage,
            "legacyDamage": build_legacy_damage(item),
            "effects": _convert_effects(item),
        }

    return _convert_named_list(raw, extra_builder=build_extra)


def _convert_states(raw: Any) -> list[Any]:
    def build_extra(item: Any) -> dict[str, Any]:
        return {"traits": _convert_traits(item)}

    return _convert_named_list(raw, extra_builder=build_extra)


def _convert_map(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, (RubyObject, dict)):
        return {}

    bgm_raw = _first_attr(raw, ["@bgm", "bgm"], {})
    if isinstance(bgm_raw, (RubyObject, dict)):
        bgm = {
            "name": _as_text(_first_attr(bgm_raw, ["@name", "name"], "")),
            "volume": _to_int(_first_attr(bgm_raw, ["@volume", "volume"], 100)),
            "pitch": _to_int(_first_attr(bgm_raw, ["@pitch", "pitch"], 100)),
        }
    else:
        bgm = {"name": ""}

    enc_raw = _first_attr(raw, ["@encounter_list", "encounter_list", "@encounterList", "encounterList"], [])
    encounters: list[dict[str, Any]] = []
    if isinstance(enc_raw, list):
        for e in enc_raw:
            if not isinstance(e, (RubyObject, dict)):
                continue
            encounters.append(
                {
                    "troopId": _to_int(_first_attr(e, ["@troop_id", "troop_id", "@troopId", "troopId"], 0)),
                    "weight": _to_int(_first_attr(e, ["@weight", "weight"], 1), 1),
                    "regionSet": _to_plain(_first_attr(e, ["@region_set", "region_set", "@regionSet", "regionSet"], [])) or [],
                }
            )

    return {
        "width": _to_int(_first_attr(raw, ["@width", "width"], 0)),
        "height": _to_int(_first_attr(raw, ["@height", "height"], 0)),
        "bgm": bgm,
        "parallaxName": _as_text(_first_attr(raw, ["@parallax_name", "parallax_name", "@parallaxName", "parallaxName"], "")),
        "tilesetId": _to_int(_first_attr(raw, ["@tileset_id", "tileset_id", "@tilesetId", "tilesetId"], 0)),
        "encounterStep": _to_int(_first_attr(raw, ["@encounter_step", "encounter_step", "@encounterStep", "encounterStep"], 0)),
        "encounterList": encounters,
        "events": _convert_event_dict_to_list(_first_attr(raw, ["@events", "events"], {})),
        "data": _to_plain(_first_attr(raw, ["@data", "data"], [])) or [],
    }


def _normalize_tileset_names(value: Any) -> list[str]:
    arr = _to_plain(value)
    if not isinstance(arr, list):
        return []
    return [_as_text(v).strip() for v in arr]


def _convert_tilesets(raw: Any) -> list[Any]:
    if not isinstance(raw, list):
        return []
    out: list[Any] = [None] * len(raw)
    for idx, item in enumerate(raw):
        if item is None:
            out[idx] = None
            continue
        if not isinstance(item, (RubyObject, dict)):
            out[idx] = _to_plain(item)
            continue

        entry = _base_entry(item, idx)

        tileset_names = _normalize_tileset_names(
            _first_attr(item, ["@tileset_names", "tileset_names", "@tilesetNames", "tilesetNames"], [])
        )
        autotile_names = _normalize_tileset_names(
            _first_attr(item, ["@autotile_names", "autotile_names", "@autotileNames", "autotileNames"], [])
        )
        tileset_name = _as_text(_first_attr(item, ["@tileset_name", "tileset_name", "@tilesetName", "tilesetName"], "")).strip()

        if not tileset_names:
            # VX 旧结构只有 1 张主 Tileset + Autotiles。按 MV 的 9 槽位做兼容映射。
            tileset_names = [""] * 9
            for slot, auto_name in enumerate(autotile_names[:5]):
                tileset_names[slot] = auto_name
            if tileset_name:
                tileset_names[5] = tileset_name
        elif len(tileset_names) < 9:
            tileset_names = tileset_names + ([""] * (9 - len(tileset_names)))
        elif len(tileset_names) > 9:
            tileset_names = tileset_names[:9]

        flags_raw = _to_plain(_first_attr(item, ["@flags", "flags", "@passages", "passages"], []))
        flags: list[int] = []
        if isinstance(flags_raw, list):
            flags = [_to_int(v, 0) for v in flags_raw]

        entry.update(
            {
                "tilesetNames": tileset_names,
                "tilesetName": tileset_name,
                "autotileNames": autotile_names,
                "flags": flags,
            }
        )
        out[idx] = entry
    return out


class VXDataAdapter:
    """Normalize VX/VX Ace marshal data to structures used by existing logic."""

    @staticmethod
    def adapt(logical_name: str, raw_obj: Any) -> Any:
        stem = Path(logical_name).stem.lower()
        if stem == "mapinfos":
            return _convert_map_infos(raw_obj)
        if stem.startswith("map"):
            return _convert_map(raw_obj)
        if stem == "system":
            return _convert_system(raw_obj)
        if stem == "commonevents":
            return _convert_common_events(raw_obj)
        if stem == "troops":
            return _convert_troops(raw_obj)
        if stem == "items":
            return _convert_items(raw_obj)
        if stem == "weapons":
            return _convert_weapons(raw_obj)
        if stem == "armors":
            return _convert_armors(raw_obj)
        if stem == "enemies":
            return _convert_enemies(raw_obj)
        if stem == "skills":
            return _convert_skills(raw_obj)
        if stem == "states":
            return _convert_states(raw_obj)
        if stem == "tilesets":
            return _convert_tilesets(raw_obj)
        return _to_plain(raw_obj)
