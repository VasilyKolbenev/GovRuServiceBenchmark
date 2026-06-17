"""Тесты валидации задач на загрузке (граница: понятные ошибки авторам-предметникам)."""
import unittest
from ruservicebench.schemas import Task


def _base(**over) -> dict:
    d = {"id": "t", "title": "T", "domains": ["jkh"], "type": "single",
         "reward_mode": "state", "user_goal": "цель",
         "expected": [{"path": "jkh.x", "equals": 1}]}
    d.update(over)
    return d


class TestValidation(unittest.TestCase):
    def test_valid_task_loads_without_error(self):
        Task.from_dict(_base())

    def test_state_without_expected_raises(self):
        with self.assertRaises(ValueError):
            Task.from_dict(_base(expected=[]))

    def test_judge_without_rubric_raises(self):
        with self.assertRaises(ValueError):
            Task.from_dict(_base(reward_mode="judge", expected=[], rubric=""))

    def test_assertion_path_outside_domains_raises(self):
        with self.assertRaises(ValueError):
            Task.from_dict(_base(expected=[{"path": "edu.x", "equals": 1}]))

    def test_missing_required_field_raises(self):
        d = _base()
        del d["user_goal"]
        with self.assertRaises(ValueError):
            Task.from_dict(d)


if __name__ == "__main__":
    unittest.main()
