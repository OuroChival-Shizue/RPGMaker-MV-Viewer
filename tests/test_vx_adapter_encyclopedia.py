from __future__ import annotations

import unittest

from viewer.database import DatabaseManager
from viewer.encyclopedia import build_encyclopedia
from viewer.vx_adapter import VXDataAdapter


class _FakeLoader:
    def __init__(self, payload):
        self.payload = payload
        self.engine = "vxace"

    def load_json(self, filename: str):
        return self.payload.get(filename)


class VxAdapterEncyclopediaTest(unittest.TestCase):
    def test_vx_adapted_data_is_not_default_only(self):
        raw_items = [
            None,
            {
                "@id": 1,
                "@name": "药草",
                "@description": "恢复HP",
                "@price": 35,
                "@itype_id": 1,
                "@icon_index": 16,
                "@consumable": True,
                "@scope": 7,
                "@effects": [{"@code": 11, "@data_id": 0, "@value1": 0, "@value2": 50}],
            },
        ]
        raw_weapons = [
            None,
            {
                "@id": 1,
                "@name": "木剑",
                "@price": 120,
                "@wtype_id": 1,
                "@icon_index": 33,
                "@params": [0, 0, 12, 0, 0, 0, 0, 0],
                "@features": [{"@code": 21, "@data_id": 2, "@value": 1.1}],
            },
        ]
        raw_armors = [
            None,
            {
                "@id": 1,
                "@name": "布衣",
                "@price": 80,
                "@atype_id": 1,
                "@etype_id": 3,
                "@icon_index": 45,
                "@params": [0, 0, 0, 9, 0, 0, 0, 0],
            },
        ]
        raw_enemies = [
            None,
            {
                "@id": 1,
                "@name": "史莱姆",
                "@exp": 14,
                "@gold": 6,
                "@battler_name": "Slime",
                "@drop_items": [{"@kind": 1, "@data_id": 1, "@denominator": 2}],
                "@actions": [{"@skill_id": 1, "@rating": 5}],
                "@params": [50, 10, 8, 6, 4, 3, 5, 2],
            },
        ]
        raw_skills = [
            None,
            {
                "@id": 1,
                "@name": "火球",
                "@stype_id": 1,
                "@icon_index": 90,
                "@scope": 1,
                "@mp_cost": 5,
                "@base_damage": 100,
                "@atk_f": 20,
                "@spi_f": 80,
                "@variance": 15,
                "@hit": 95,
            },
        ]

        payload = {
            "Items.json": VXDataAdapter.adapt("Items.json", raw_items),
            "Weapons.json": VXDataAdapter.adapt("Weapons.json", raw_weapons),
            "Armors.json": VXDataAdapter.adapt("Armors.json", raw_armors),
            "Enemies.json": VXDataAdapter.adapt("Enemies.json", raw_enemies),
            "Skills.json": VXDataAdapter.adapt("Skills.json", raw_skills),
            "States.json": [],
            "Troops.json": [],
            "System.json": {
                "switches": [],
                "variables": [],
                "elements": [],
                "weaponTypes": ["", "剑"],
                "armorTypes": ["", "轻甲"],
                "equipTypes": ["", "武器", "盾牌", "身体"],
                "skillTypes": ["", "魔法"],
            },
            "MapInfos.json": [],
            "CommonEvents.json": [],
            "Tilesets.json": [],
        }

        db = DatabaseManager(_FakeLoader(payload))
        enc = build_encyclopedia(db)

        self.assertEqual(enc["items"][0]["price"], 35)
        self.assertEqual(enc["items"][0]["iconIndex"], 16)
        self.assertTrue(enc["items"][0]["effects"])

        self.assertEqual(enc["weapons"][0]["price"], 120)
        self.assertEqual(enc["weapons"][0]["iconIndex"], 33)
        self.assertTrue(any(p["name"] == "攻击力" and p["value"] == 12 for p in enc["weapons"][0]["params"]))

        self.assertEqual(enc["enemies"][0]["exp"], 14)
        self.assertEqual(enc["enemies"][0]["gold"], 6)
        self.assertTrue(enc["enemies"][0]["drops"])
        self.assertEqual(enc["enemies"][0]["actions"][0]["skill"], "火球")
        self.assertEqual(enc["enemies"][0]["actions"][0]["skillId"], 1)
        self.assertEqual(enc["enemies"][0]["battlerName"], "Slime")
        self.assertEqual(enc["skills"][0]["name"], "火球")
        self.assertEqual(enc["skills"][0]["mpCost"], 5)
        self.assertIsNotNone(enc["skills"][0]["legacyDamage"])
        self.assertTrue(enc["skills"][0]["formulaTips"])

    def test_tilesets_support_vxace_tileset_names(self):
        raw_tilesets = [
            None,
            {
                "@id": 1,
                "@name": "Outside",
                "@tileset_names": ["Out_A1", "Out_A2", "Out_A3", "Out_A4", "Out_A5", "Out_B", "Out_C", "Out_D", "Out_E"],
                "@flags": [0, 1, 2],
            },
        ]
        adapted = VXDataAdapter.adapt("Tilesets.json", raw_tilesets)
        self.assertIsInstance(adapted, list)
        self.assertEqual(adapted[1]["tilesetNames"][0], "Out_A1")
        self.assertEqual(adapted[1]["tilesetNames"][8], "Out_E")
        self.assertEqual(adapted[1]["flags"][:3], [0, 1, 2])

    def test_tilesets_support_legacy_vx_fallback(self):
        raw_tilesets = [
            None,
            {
                "@id": 1,
                "@name": "LegacyVX",
                "@autotile_names": ["Auto_1", "Auto_2", "Auto_3"],
                "@tileset_name": "Main_01",
            },
        ]
        adapted = VXDataAdapter.adapt("Tilesets.json", raw_tilesets)
        self.assertIsInstance(adapted, list)
        self.assertEqual(adapted[1]["tilesetNames"][0], "Auto_1")
        self.assertEqual(adapted[1]["tilesetNames"][1], "Auto_2")
        self.assertEqual(adapted[1]["tilesetNames"][5], "Main_01")


if __name__ == "__main__":
    unittest.main()
