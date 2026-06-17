"""Отчёт: markdown-сводка (pass^k, разрезы, по задачам) + CSV всех прогонов."""
from __future__ import annotations
import csv
import json
from typing import Any
from .schemas import RunResult


def write_csv(runs: list[RunResult], path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["task_id", "run_idx", "success", "n_tool_calls", "judge_score",
                                          "failure_class", "llm_calls", "tokens", "latency_s", "detail", "error"])
        w.writeheader()
        for r in runs:
            w.writerow(r.to_row())


def write_markdown(summary: dict[str, Any], agent_name: str, path: str):
    L = []
    L.append(f"# RuServiceBench — отчёт ({agent_name})\n")
    L.append(f"- Задач: **{summary['n_tasks']}**, прогонов на задачу: **n={summary.get('runs_per_task', '?')}**, "
             f"кривая до **k={summary['k_max']}**\n")

    L.append(f"\n## Надёжность: pass^k (n={summary.get('runs_per_task', '?')} прогонов на задачу)\n")
    L.append("| k | pass^k | 95% ДИ |\n|---|--------|--------|")
    ci = summary.get("passk_ci", {})
    for k, v in summary["passk_curve"].items():
        lo, hi = ci.get(k, [v, v])
        L.append(f"| {k} | {v:.2%} | {lo:.0%}–{hi:.0%} |")

    L.append("\n## По типу задач\n")
    L.append(f"| Тип | pass^1 | pass^{summary['k_max']} | задач |\n|---|---|---|---|")
    for t, v in summary["by_type"].items():
        L.append(f"| {t} | {v['pass^1']:.0%} | {v[f'pass^{summary['k_max']}']:.0%} | {v['n_tasks']} |")

    L.append("\n## По доменам\n")
    L.append(f"| Домен | pass^1 | pass^{summary['k_max']} | задач |\n|---|---|---|---|")
    for d, v in summary["by_domain"].items():
        L.append(f"| {d} | {v['pass^1']:.0%} | {v[f'pass^{summary['k_max']}']:.0%} | {v['n_tasks']} |")

    L.append("\n## По задачам\n")
    L.append(f"| Задача | успехов/прогонов | pass^1 | pass^{summary['k_max']} |\n|---|---|---|---|")
    for tid, v in summary["per_task"].items():
        L.append(f"| {tid} | {v['successes']}/{v['runs']} | {v['pass^1']:.0%} | {v[f'pass^{summary['k_max']}']:.0%} |")

    c = summary.get("cost", {})
    L.append("\n## Стоимость и скорость\n")
    L.append(f"- Прогонов: **{c.get('n_runs', 0)}** · LLM-вызовов: **{c.get('llm_calls', 0)}** · "
             f"токенов: **{c.get('tokens', 0)}**")
    L.append(f"- В среднем на прогон: **{c.get('avg_tokens_per_run', 0)}** токенов, "
             f"**{c.get('avg_latency_s', 0)} с**")

    fc = summary.get("failure_classes", {})
    if fc:
        L.append("\n## Причины провалов\n")
        L.append("| Причина | Прогонов |\n|---|---|")
        for cls, n in sorted(fc.items(), key=lambda kv: -kv[1]):
            L.append(f"| {cls} | {n} |")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def write_json(summary: dict[str, Any], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
