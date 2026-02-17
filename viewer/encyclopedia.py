"""Encyclopedia translation helpers."""

from __future__ import annotations

from .database import DatabaseManager

PARAM_NAMES = ["最大HP", "最大MP", "攻击力", "防御力", "魔法攻击", "魔法防御", "敏捷", "幸运"]
XPARAM_NAMES = ["命中率", "回避率", "暴击率", "暴击回避", "魔法回避", "魔法反射",
                 "反击率", "HP再生", "MP再生", "TP再生"]
SPARAM_NAMES = ["受击率", "防御效果", "恢复效果", "药理知识", "MP消耗率",
                "TP补充率", "物理伤害率", "魔法伤害率", "地形伤害率", "经验获取率"]
OCCASION_MAP = {0: "随时", 1: "战斗中", 2: "菜单中", 3: "无法使用"}
HIT_TYPE_MAP = {0: "必中", 1: "物理", 2: "魔法"}
DAMAGE_TYPE_MAP = {
    0: "无",
    1: "HP伤害",
    2: "MP伤害",
    3: "HP恢复",
    4: "MP恢复",
    5: "HP吸收",
    6: "MP吸收",
}


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


def _safe_name(arr, idx, fallback="?"):
    try:
        if isinstance(arr, list) and 0 <= idx < len(arr):
            name = arr[idx]
            if isinstance(name, str) and name.strip():
                return name.strip()
    except Exception:  # noqa: BLE001
        pass
    return fallback


def _formula_pretty(formula: str) -> str:
    text = (formula or "").strip()
    if not text:
        return ""
    return (
        text.replace("a.", "使用者.")
        .replace("b.", "目标.")
        .replace("v[", "变量[")
        .replace("v [", "变量[")
    )


def _extract_skill_damage(skill, db):
    damage = skill.get("damage")
    if isinstance(damage, dict) and damage:
        dtype = int(damage.get("type", 0) or 0)
        eid = int(damage.get("elementId", -1) or -1)
        formula = str(damage.get("formula", "") or "").strip()
        variance = int(damage.get("variance", 0) or 0)
        critical = bool(damage.get("critical", False))
        if eid == -1:
            element = "普通攻击属性"
        elif eid == 0:
            element = "无属性"
        else:
            element = db.get_element_name(eid)
        return {
            "damageType": DAMAGE_TYPE_MAP.get(dtype, f"类型#{dtype}"),
            "damageElement": element,
            "damageVariance": variance,
            "damageCritical": critical,
            "formula": formula,
            "formulaPretty": _formula_pretty(formula),
            "formulaTips": [
                "a = 使用者，b = 目标",
                "变量写法: 变量[n]（原公式 v[n]）",
            ] if formula else [],
            "legacyDamage": None,
        }

    # VX 旧版：无公式脚本，按参数机制结算
    legacy = skill.get("legacyDamage")
    if isinstance(legacy, dict):
        base = int(legacy.get("baseDamage", 0) or 0)
        atk_f = int(legacy.get("atkF", 0) or 0)
        spi_f = int(legacy.get("spiF", 0) or 0)
        var = int(legacy.get("variance", 0) or 0)
        elem_set = legacy.get("elementSet", [])
        elems = []
        if isinstance(elem_set, list):
            for eid in elem_set:
                try:
                    elems.append(db.get_element_name(int(eid)))
                except Exception:  # noqa: BLE001
                    continue
        return {
            "damageType": "引擎旧版伤害",
            "damageElement": "、".join(elems) if elems else "按技能属性",
            "damageVariance": var,
            "damageCritical": False,
            "formula": "",
            "formulaPretty": "",
            "formulaTips": [
                "VX 旧版技能通常不使用脚本公式",
                "由基础伤害 + 能力系数 + 波动值组成",
            ],
            "legacyDamage": {
                "baseDamage": base,
                "atkF": atk_f,
                "spiF": spi_f,
                "variance": var,
            },
        }

    return {
        "damageType": "未知",
        "damageElement": "?",
        "damageVariance": 0,
        "damageCritical": False,
        "formula": "",
        "formulaPretty": "",
        "formulaTips": [],
        "legacyDamage": None,
    }


def build_encyclopedia(db, asset_resolver=None):
    """构建图鉴数据，返回 {weapons, armors, items, enemies, skills}"""
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
            "iconIndex": w.get("iconIndex", 0),
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
            "iconIndex": a.get("iconIndex", 0),
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
            "iconIndex": it.get("iconIndex", 0),
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
            actions.append({"skill": db.get_skill_name(sid), "skillId": sid, "rating": r})
        portrait_rel = ""
        if asset_resolver:
            try:
                portrait_rel = asset_resolver.resolve_enemy_portrait_rel(en) or ""
            except Exception:  # noqa: BLE001
                portrait_rel = ""
        enemies.append({
            "id": en["id"], "name": en["name"],
            "params": proc_params(en.get("params")),
            "exp": en.get("exp", 0), "gold": en.get("gold", 0),
            "drops": drops, "actions": actions,
            "traits": proc_traits(en.get("traits")),
            "iconIndex": en.get("iconIndex", 0),
            "battlerName": en.get("battlerName", ""),
            "battlerHue": en.get("battlerHue", 0),
            "portraitRel": portrait_rel,
        })

    # --- 技能 ---
    skills = []
    for sk in db.raw_skills:
        if not sk or not isinstance(sk, dict) or not sk.get("name", "").strip():
            continue
        stype_id = int(sk.get("stypeId", 0) or 0)
        damage_meta = _extract_skill_damage(sk, db)
        skills.append(
            {
                "id": sk.get("id", 0),
                "name": sk.get("name", ""),
                "desc": sk.get("description", ""),
                "iconIndex": sk.get("iconIndex", 0),
                "stype": _safe_name(db.skill_types, stype_id, f"类型#{stype_id}"),
                "scope": scope_map.get(int(sk.get("scope", 0) or 0), "?"),
                "occasion": OCCASION_MAP.get(int(sk.get("occasion", 0) or 0), "?"),
                "hitType": HIT_TYPE_MAP.get(int(sk.get("hitType", 0) or 0), "?"),
                "mpCost": int(sk.get("mpCost", 0) or 0),
                "tpCost": int(sk.get("tpCost", 0) or 0),
                "tpGain": int(sk.get("tpGain", 0) or 0),
                "speed": int(sk.get("speed", 0) or 0),
                "repeats": int(sk.get("repeats", 1) or 1),
                "successRate": int(sk.get("successRate", 100) or 100),
                "effects": [translate_effect(e, db) for e in (sk.get("effects") or [])],
                **damage_meta,
            }
        )

    return {"weapons": weapons, "armors": armors, "items": items, "enemies": enemies, "skills": skills}
