"""Тесты оценщика: разрешение dotted-путей, вердикт судьи, таксономия провалов."""
import unittest
from ruservicebench.evaluator import _resolve, _verdict, classify_failure
from ruservicebench.schemas import Task, RunResult, ToolCall, TaskType, RewardMode


def _task(reward: RewardMode, ttype: TaskType) -> Task:
    return Task(id="t", title="t", domains=["jkh"], type=ttype, reward_mode=reward, user_goal="x")


class TestResolve(unittest.TestCase):
    def test_resolve_nested_dict_and_list_index(self):
        state = {"jkh": {"accounts": {"1": {"charges": [{"paid": True}]}}}}
        self.assertEqual(_resolve(state, "jkh.accounts.1.charges.0.paid"), True)

    def test_resolve_missing_path_returns_none(self):
        self.assertIsNone(_resolve({"a": 1}, "a.b.c"))


class TestVerdict(unittest.TestCase):
    def test_verdict_pass_on_first_line(self):
        self.assertTrue(_verdict("PASS\nцель достигнута"))

    def test_verdict_fail_on_first_line(self):
        self.assertFalse(_verdict("FAIL\nагент не выполнил"))

    def test_verdict_pass_word_in_fail_reasoning_stays_fail(self):
        self.assertFalse(_verdict("FAIL\nкритерий PASS не выполнен"))


class TestClassifyFailure(unittest.TestCase):
    def test_classify_exception(self):
        r = RunResult(task_id="t", run_idx=0, error="boom")
        self.assertEqual(classify_failure(_task(RewardMode.STATE, TaskType.SINGLE), r), "exception")

    def test_classify_tool_error(self):
        r = RunResult(task_id="t", run_idx=0)
        r.tool_calls.append(ToolCall("x", {}, "err", ok=False))
        self.assertEqual(classify_failure(_task(RewardMode.STATE, TaskType.SINGLE), r), "tool_error")

    def test_classify_no_action(self):
        r = RunResult(task_id="t", run_idx=0)
        self.assertEqual(classify_failure(_task(RewardMode.STATE, TaskType.SINGLE), r), "no_action")

    def test_classify_wrong_outcome(self):
        r = RunResult(task_id="t", run_idx=0)
        r.tool_calls.append(ToolCall("x", {}, "ok", ok=True))
        self.assertEqual(classify_failure(_task(RewardMode.STATE, TaskType.SINGLE), r), "wrong_outcome")

    def test_classify_judge_fail(self):
        r = RunResult(task_id="t", run_idx=0)
        self.assertEqual(classify_failure(_task(RewardMode.JUDGE, TaskType.PROACTIVE), r), "judge_fail")


if __name__ == "__main__":
    unittest.main()
