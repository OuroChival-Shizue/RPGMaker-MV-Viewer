from __future__ import annotations

import unittest

from viewer.database import DatabaseManager


class _FakeLoader:
    def __init__(self, payload):
        self.payload = payload
        self.engine = "vxace"

    def load_json(self, filename: str):
        return self.payload.get(filename)


def _base_payload(tilesets):
    return {
        "Items.json": [],
        "Weapons.json": [],
        "Armors.json": [],
        "Enemies.json": [],
        "Skills.json": [],
        "States.json": [],
        "Troops.json": [],
        "System.json": {},
        "MapInfos.json": [],
        "CommonEvents.json": [],
        "Tilesets.json": tilesets,
    }


class DatabaseTilesetNamesTest(unittest.TestCase):
    def test_prefers_tileset_names_field(self):
        payload = _base_payload(
            [
                None,
                {
                    "id": 1,
                    "name": "Outside",
                    "tilesetNames": ["Out_A1", "Out_A2", "Out_A3", "Out_A4", "Out_A5", "Out_B", "Out_C", "Out_D", "Out_E"],
                },
            ]
        )
        db = DatabaseManager(_FakeLoader(payload))
        names = db.get_tileset_names(1)
        self.assertEqual(names[0], "Out_A1")
        self.assertEqual(names[8], "Out_E")

    def test_fallback_from_legacy_vx_fields(self):
        payload = _base_payload(
            [
                None,
                {
                    "id": 7,
                    "name": "Legacy",
                    "autotileNames": ["Auto1", "Auto2", "Auto3"],
                    "tilesetName": "Dungeon",
                },
            ]
        )
        db = DatabaseManager(_FakeLoader(payload))
        names = db.get_tileset_names(7)
        self.assertEqual(len(names), 9)
        self.assertEqual(names[0], "Auto1")
        self.assertEqual(names[1], "Auto2")
        self.assertEqual(names[5], "Dungeon")


if __name__ == "__main__":
    unittest.main()
