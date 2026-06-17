"""Тесты математики надёжности: pass^k, доверительный интервал, агрегация."""
import unittest
from ruservicebench.metrics import _pass_hat_k, _ci95, aggregate
from ruservicebench.schemas import Task, RunResult, TaskType, RewardMode


def _task(tid: str) -> Task:
    return Task(id=tid, title=tid, domains=["jkh"], type=TaskType.SINGLE,
                reward_mode=RewardMode.STATE, user_goal="x")


def _runs(tid: str, successes: int, n: int) -> list[RunResult]:
    return [RunResult(task_id=tid, run_idx=i, success=(i < successes)) for i in range(n)]


class TestPassHatK(unittest.TestCase):
    def test_passhatk_all_success_returns_one(self):
        self.assertEqual(_pass_hat_k(10, 10, 5), 1.0)

    def test_passhatk_c_less_than_k_returns_zero(self):
        self.assertEqual(_pass_hat_k(10, 3, 5), 0.0)

    def test_passhatk_k_greater_than_n_all_success(self):
        self.assertEqual(_pass_hat_k(3, 3, 5), 1.0)

    def test_passhatk_k_greater_than_n_partial_returns_zero(self):
        self.assertEqual(_pass_hat_k(3, 2, 5), 0.0)

    def test_passhatk_half_success_known_value(self):
        self.assertAlmostEqual(_pass_hat_k(4, 2, 2), 1 / 6)  # C(2,2)/C(4,2)


class TestCI(unittest.TestCase):
    def test_ci95_empty_returns_zeros(self):
        self.assertEqual(_ci95([]), [0.0, 0.0])

    def test_ci95_single_returns_point(self):
        self.assertEqual(_ci95([0.5]), [0.5, 0.5])

    def test_ci95_zero_variance_returns_point(self):
        self.assertEqual(_ci95([1.0, 1.0, 1.0]), [1.0, 1.0])

    def test_ci95_bounds_clamped_to_unit_interval(self):
        lo, hi = _ci95([0.0, 1.0, 0.0, 1.0])
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)


class TestAggregate(unittest.TestCase):
    def test_aggregate_exposes_ci_cost_and_failures(self):
        runs = _runs("a", successes=6, n=10)
        for r in runs:
            if not r.success:
                r.failure_class = "wrong_outcome"
        s = aggregate([_task("a")], runs, k_max=5)
        self.assertEqual(s["n_tasks"], 1)
        self.assertEqual(s["runs_per_task"], 10)
        self.assertAlmostEqual(s["passk_curve"][1], 0.6, places=4)
        self.assertIn(1, s["passk_ci"])
        self.assertEqual(s["cost"]["n_runs"], 10)
        self.assertEqual(s["failure_classes"].get("wrong_outcome"), 4)


if __name__ == "__main__":
    unittest.main()
