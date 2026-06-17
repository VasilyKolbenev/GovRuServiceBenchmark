"""Раннер: гоняет каждую задачу k раз, оценивает, агрегирует pass^k."""
from __future__ import annotations
from typing import Any
from .environments import Environment
from .simulator import UserSimulator
from .agents import Agent
from .evaluator import evaluate, classify_failure
from .metrics import aggregate
from .schemas import Task, RunResult
from .llm import LLMClient


def _usage(clients: list[LLMClient]) -> dict[str, float]:
    agg = {"calls": 0.0, "prompt_tokens": 0.0, "completion_tokens": 0.0, "latency_s": 0.0}
    for c in clients:
        for key, val in c.usage_snapshot().items():
            agg[key] += val
    return agg


def _apply_usage(res: RunResult, before: dict[str, float], clients: list[LLMClient]) -> None:
    after = _usage(clients)
    res.llm_calls = int(after["calls"] - before["calls"])
    res.prompt_tokens = int(after["prompt_tokens"] - before["prompt_tokens"])
    res.completion_tokens = int(after["completion_tokens"] - before["completion_tokens"])
    res.latency_s = after["latency_s"] - before["latency_s"]


def run_suite(tasks: list[Task], agent: Agent, llm: LLMClient, judge_llm: LLMClient | None = None,
              runs: int = 10, k_max: int = 5,
              scripted_user: bool = False) -> tuple[list[RunResult], dict[str, Any]]:
    judge_llm = judge_llm or llm
    clients = [llm] if judge_llm is llm else [llm, judge_llm]
    results: list[RunResult] = []
    for task in tasks:
        for i in range(runs):
            env = Environment(task.domains)
            env.reset(task.initial_state)
            user = UserSimulator(task, llm, scripted=scripted_user)
            before = _usage(clients)
            try:
                res = agent.run(task, env, user)
                res.task_id, res.run_idx = task.id, i
                res = evaluate(task, res, judge_llm)
            except NotImplementedError as e:
                res = RunResult(task_id=task.id, run_idx=i, success=False, error=f"NotImplemented: {e}")
            except Exception as e:  # noqa — изолируем падение одного прогона, метрика остаётся устойчивой
                res = RunResult(task_id=task.id, run_idx=i, success=False, error=str(e))
            _apply_usage(res, before, clients)
            if not res.success:
                res.failure_class = classify_failure(task, res)
            results.append(res)
    summary = aggregate(tasks, results, k_max=k_max)
    return results, summary
