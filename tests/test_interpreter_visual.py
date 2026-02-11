from __future__ import annotations

import unittest

from viewer.interpreter import EventInterpreter


class _DummyDb:
    def get_switch_name(self, _sid):
        return ""

    def get_variable_name(self, _vid):
        return ""

    def get_item_name(self, _iid):
        return ""


class InterpreterVisualTest(unittest.TestCase):
    def test_parse_page_visual_includes_direction_and_pattern(self):
        result = EventInterpreter._parse_page_visual(
            {
                "characterName": "Actor1",
                "characterIndex": 5,
                "direction": 4,
                "pattern": 2,
                "isBigCharacter": False,
            },
            "",
            0,
        )
        self.assertEqual(result["characterName"], "Actor1")
        self.assertEqual(result["characterIndex"], 5)
        self.assertEqual(result["direction"], 4)
        self.assertEqual(result["pattern"], 2)

    def test_interpret_page_visual_uses_face_command(self):
        interpreter = EventInterpreter(_DummyDb())
        evt = {
            "id": 1,
            "name": "E1",
            "x": 1,
            "y": 2,
            "pages": [
                {
                    "trigger": 0,
                    "conditions": {},
                    "image": {"characterName": "Actor2", "characterIndex": 3},
                    "list": [{"code": 101, "parameters": ["FaceA", 1, 0, 2], "indent": 0}],
                }
            ],
        }
        parsed = interpreter.interpret_event(evt)
        visual = parsed["pages"][0]["visual"]
        self.assertEqual(visual["faceName"], "FaceA")
        self.assertEqual(visual["faceIndex"], 1)


if __name__ == "__main__":
    unittest.main()
