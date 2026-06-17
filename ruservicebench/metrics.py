"""Метрики надёжности. Главная — pass^k (в стиле tau-bench): вероятность, что
агент решит задачу во ВСЕХ k запусках. Несмещённая оценка по n прогонам с c успехами:
    pass^k(task) = C(c, k) / C(n, k)     (если n >= k; иначе 1.0 при c==n, иначе 0.0)
Итоговый pass^k — среднее по задачам. pass^1 = обычный success rate."""
from __future__ import annotations
from math import comb
from statistics import stdev
from collections import defaultdict
from typing import Any
from .schemas import RunResult, Task


def _pass_hat_k(n: int, c: int, k: int) -> float:
    if k > n:
        return 1.0 if c == n else 0.0
    if c < k:
        return 0.0
    return comb(c, k) / comb(n, k)


def _ci95(values: list[float]) -> list[float]:
    """95%-доверительный интервал среднего по задачам (нормальное приближение, SE = s/√N).
    Грубо при малом числе задач — честно показывает разброс, а не точечную цифру."""
    n = len(values)
    if n == 0:
        return [0.0, 0.0]
    m = sum(values) / n
    if n < 2:
        return [round(m, 4), round(m, 4)]
    half = 1.96 * stdev(values) / (n ** 0.5)
    return [round(max(0.0, m - half), 4), round(min(1.0, m + half), 4)]


def aggregate(tasks: list[Task], runs: list[RunResult], k_max: int) -> dict[str, Any]:
    by_task: dict[str, list[bool]] = defaultdict(list)
    for r in runs:
        by_task[r.task_id].append(r.success)
    task_index = {t.id: t for t in tasks}

    # pass^k кривая (среднее по задачам) + доверительный интервал
    passk = {}
    passk_ci = {}
    for k in range(1, k_max + 1):
        vals = [_pass_hat_k(len(s), sum(s), k) for s in by_task.values()]
        passk[k] = round(sum(vals) / len(vals), 4) if vals else 0.0
        passk_ci[k] = _ci95(vals)

    # разрезы по типу и домену (по pass^1 и pass^k_max)
    def bucket(keyfn):
        agg = defaultdict(lambda: {"p1": [], "pk": []})
        for tid, s in by_task.items():
            key = keyfn(task_index[tid])
            agg[key]["p1"].append(_pass_hat_k(len(s), sum(s), 1))
            agg[key]["pk"].append(_pass_hat_k(len(s), sum(s), k_max))
        return {k: {"pass^1": round(sum(v["p1"]) / len(v["p1"]), 4),
                    f"pass^{k_max}": round(sum(v["pk"]) / len(v["pk"]), 4),
                    "n_tasks": len(v["p1"])} for k, v in agg.items()}

    # таксономия провалов + стоимость/скорость по всем прогонам
    fails: dict[str, int] = defaultdict(int)
    for r in runs:
        if not r.success:
            fails[r.failure_class or "unknown"] += 1
    n_runs = len(runs)
    tokens = sum(r.prompt_tokens + r.completion_tokens for r in runs)
    cost = {
        "n_runs": n_runs,
        "llm_calls": sum(r.llm_calls for r in runs),
        "tokens": tokens,
        "avg_tokens_per_run": round(tokens / n_runs) if n_runs else 0,
        "avg_latency_s": round(sum(r.latency_s for r in runs) / n_runs, 2) if n_runs else 0.0,
    }

    return {
        "n_tasks": len(by_task),
        "n_runs": n_runs,
        "runs_per_task": (n_runs // len(by_task)) if by_task else 0,
        "k_max": k_max,
        "passk_curve": passk,
        "passk_ci": passk_ci,
        "cost": cost,
        "failure_classes": dict(fails),
        "by_type": bucket(lambda t: t.type.value),
        "by_domain": bucket(lambda t: "+".join(t.domains)),
        "per_task": {tid: {"runs": len(s), "successes": sum(s),
                           "pass^1": round(_pass_hat_k(len(s), sum(s), 1), 3),
                           f"pass^{k_max}": round(_pass_hat_k(len(s), sum(s), k_max), 3)}
                     for tid, s in by_task.items()},
    }
