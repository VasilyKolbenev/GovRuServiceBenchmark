"""Тесты устойчивого парсера действий ReAct-агента."""
import unittest
from ruservicebench.agents import _parse_action


class TestParseAction(unittest.TestCase):
    def test_parse_plain_json_tool_action(self):
        a = _parse_action('{"action":"tool","tool":"jkh_pay_charge","args":{"id":"1"}}')
        self.assertEqual(a["action"], "tool")
        self.assertEqual(a["tool"], "jkh_pay_charge")

    def test_parse_fenced_json_say_action(self):
        a = _parse_action('```json\n{"action":"say","text":"привет"}\n```')
        self.assertEqual(a["action"], "say")

    def test_parse_prose_wrapped_json(self):
        a = _parse_action('Думаю так: {"action":"done","text":"готово"} — конец.')
        self.assertEqual(a["action"], "done")

    def test_parse_non_json_falls_back_to_say(self):
        a = _parse_action("просто текст без json")
        self.assertEqual(a["action"], "say")
        self.assertIn("просто текст", a["text"])


if __name__ == "__main__":
    unittest.main()
