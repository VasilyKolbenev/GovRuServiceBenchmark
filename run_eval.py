#!/usr/bin/env python3
"""Точка входа: запуск eval-набора.

Примеры:
  # dry-run без ключей/сети — проверить пайплайн и увидеть пример отчёта с pass^k:
  python run_eval.py --dry-run --k 5

  # реальный прогон (после реализации адаптеров и настройки .env):
  python run_eval.py --agent cam1 --k 5            # baseline (старый ЦАМ)
  python run_eval.py --agent reference --k 5       # референсный агентный baseline
  python run_eval.py --agent cam2 --k 5            # новый ЦАМ 2.0 (когда запустится)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from ruservicebench.schemas import Task
from ruservicebench.environments import DOMAINS
from ruservicebench.llm import build_llm, build_judge_llm, FakeLLM
from ruservicebench.agents import build_agent, DemoAgent
from ruservicebench.runner import run_suite
from ruservicebench.report import write_csv, write_markdown, write_json
from ruservicebench.compare import save_agent_summary
from ruservicebench.portal import write_portal


def load_dotenv(path: str = ".env") -> None:
    """Минимальная загрузка .env в окружение (stdlib, без зависимостей).
    Реальные переменные окружения имеют приоритет над файлом."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def build_samples(runs: list) -> dict:
    """По одному показательному прогону на задачу (предпочтительно провальный) — для вкладки «Провалы»."""
    first: dict = {}
    failed: dict = {}
    for r in runs:
        first.setdefault(r.task_id, r)
        if not r.success:
            failed.setdefault(r.task_id, r)
    out = {}
    for tid, r0 in first.items():
        r = failed.get(tid, r0)
        out[tid] = {"failure_class": r.failure_class, "success": r.success,
                    "transcript": [{"role": t.role, "text": t.text} for t in r.transcript]}
    return out


def load_tasks(path: str) -> list[Task]:
    with open(path, encoding="utf-8") as f:
        tasks = [Task.from_dict(d) for d in json.load(f)]
    for t in tasks:
        unknown = [d for d in t.domains if d not in DOMAINS]
        if unknown:
            raise SystemExit(f"Задача {t.id!r}: неизвестные домены {unknown}. Доступно: {list(DOMAINS)}")
    return tasks


def main():
    for stream in (sys.stdout, sys.stderr):       # кириллица в консоли Windows
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    load_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="reference", choices=["demo", "reference", "cam1", "cam2"])
    ap.add_argument("--tasks", default="tasks/seed_tasks.json")
    ap.add_argument("--runs", type=int, default=10, help="прогонов на задачу (n); для pass^k нужно n>k")
    ap.add_argument("--k", type=int, default=5, help="макс. k для кривой pass^k (k<=runs)")
    ap.add_argument("--task", default="", help="прогнать только задачи, чей id содержит подстроку")
    ap.add_argument("--limit", type=int, default=0, help="ограничить число задач (0 = все)")
    ap.add_argument("--out", default="out")
    ap.add_argument("--dry-run", action="store_true", help="DemoAgent + FakeLLM, без сети/ключей")
    ap.add_argument("--failure-rate", type=float, default=0.25, help="имитация нестабильности в dry-run")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    tasks = load_tasks(args.tasks)
    if args.task:
        tasks = [t for t in tasks if args.task in t.id]
    if args.limit:
        tasks = tasks[:args.limit]
    if not tasks:
        raise SystemExit("Нет задач после фильтра --task/--limit.")
    k = min(args.k, args.runs)
    if k < args.k:
        print(f"[warn] k={args.k} > runs={args.runs}: pass^k обрезан до k={k}.")

    if args.dry_run:
        llm = FakeLLM()
        judge_llm = llm
        agent = DemoAgent(failure_rate=args.failure_rate, seed=42)
        scripted_user = True
        name = "dry-run/DemoAgent"
    else:
        llm = build_llm()
        judge_llm = build_judge_llm(llm)
        agent = build_agent(args.agent, llm)
        scripted_user = False
        name = args.agent

    runs, summary = run_suite(tasks, agent, llm, judge_llm=judge_llm,
                              runs=args.runs, k_max=k, scripted_user=scripted_user)
    write_csv(runs, os.path.join(args.out, "runs.csv"))
    write_json(summary, os.path.join(args.out, "summary.json"))
    write_markdown(summary, name, os.path.join(args.out, "report.md"))
    save_agent_summary(summary, name, args.out)
    portal_path = write_portal(summary, name, args.out, tasks=tasks, samples=build_samples(runs))

    print(f"Агент: {name} | задач: {summary['n_tasks']} | k={summary['k_max']}")
    print("pass^k:", summary["passk_curve"])
    print(f"Единый портал: {portal_path}")
    print(f"Отчёт (md): {os.path.join(args.out, 'report.md')}")


if __name__ == "__main__":
    main()
