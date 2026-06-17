"""Агенты под тестом. Один интерфейс — несколько реализаций:
  - DemoAgent          — детерминированный «демо»-агент для dry-run/проверки пайплайна (НЕ для метрик).
  - ReferenceReactAgent — референсный агентный baseline (ReAct + наши инструменты) на фронтир-модели. TODO.
  - Cam1Adapter         — старый ЦАМ 1.0 (классификаторы). TODO: вызов его API; обычно judge-режим.
  - Cam2Adapter         — новый ЦАМ 2.0 по A2A (Task/TaskResult). TODO: подключить, когда 2.0 запустится.
Все гоняются по одним задачам в одной песочнице -> метрики сравнимы."""
from __future__ import annotations
import json
import os
import random
from typing import Any
from .environments import Environment
from .simulator import UserSimulator
from .schemas import Task, RunResult, ToolCall, Turn
from .llm import LLMClient


class Agent:
    name = "base"

    def run(self, task: Task, env: Environment, user: UserSimulator, max_turns: int = 8) -> RunResult:
        raise NotImplementedError


class DemoAgent(Agent):
    """Исполняет task.demo_solution по шагам. Для демонстрации pass^k роняет
    последний результативный шаг с вероятностью failure_rate (имитация нестабильности)."""
    name = "demo"

    def __init__(self, failure_rate: float = 0.25, seed: int | None = None):
        self.failure_rate = failure_rate
        self.rng = random.Random(seed)

    def run(self, task, env, user, max_turns=8):
        res = RunResult(task_id=task.id, run_idx=0)
        res.transcript.append(Turn("user", user.first_message()))
        steps = list(task.demo_solution)
        drop_last = self.rng.random() < self.failure_rate
        skip_idx = (len(steps) - 1) if (drop_last and steps) else None
        for i, step in enumerate(steps):
            if i == skip_idx:
                res.transcript.append(Turn("agent", "(шаг пропущен — имитация сбоя)"))
                continue
            if "tool" in step:
                try:
                    out = env.call_tool(step["tool"], step.get("args", {}))
                    res.tool_calls.append(ToolCall(step["tool"], step.get("args", {}), out, True))
                except Exception as e:  # noqa
                    res.tool_calls.append(ToolCall(step["tool"], step.get("args", {}), str(e), False))
                    res.error = str(e)
            if "say" in step:
                res.transcript.append(Turn("agent", step["say"]))
        res.final_state = env.composite_state()
        return res


SYSTEM_PROMPT_AGENT = """Ты — ИИ-агент госуслуг. Помогаешь пользователю достичь его цели, вызывая инструменты песочницы.

Доступные инструменты:
{tools}

Протокол: на каждом шаге верни РОВНО ОДИН JSON-объект (без markdown и пояснений) одного из видов:
- вызов инструмента: {{"action": "tool", "tool": "<имя>", "args": {{...}}}}
- сообщение пользователю: {{"action": "say", "text": "..."}}
- завершение, когда цель достигнута: {{"action": "done", "text": "..."}}

Правила:
- Недостающие данные (номер счёта, показания, имя ребёнка и т.п.) спрашивай у пользователя через "say": он не выдаёт всё сразу.
- Для реальных действий вызывай инструменты, не выдумывай их результаты.
- Один шаг — один JSON. Получив результат инструмента, продолжай.
- Заверши ("done"), когда цель пользователя выполнена."""


def _format_tools(specs: list[dict[str, Any]]) -> str:
    lines = []
    for s in specs:
        params = ", ".join(f"{k}: {v}" for k, v in s.get("params", {}).items())
        lines.append(f"- {s['name']}({params}) — {s['description']}")
    return "\n".join(lines)


def _parse_action(text: str) -> dict[str, Any]:
    """Достаёт JSON-действие из ответа модели. При неудаче трактует ответ как сообщение пользователю."""
    raw = text.strip()
    candidates = [raw]
    if "{" in raw and "}" in raw:
        candidates.append(raw[raw.find("{"): raw.rfind("}") + 1])  # JSON внутри код-блока/«болтовни»
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and "action" in obj:
            return obj
    return {"action": "say", "text": raw}


def _apply_tool(env: Environment, action: dict[str, Any], res: RunResult) -> str:
    """Выполняет вызов инструмента, пишет ToolCall и возвращает текст-обратную-связь для модели."""
    tool = action.get("tool", "")
    args = action.get("args") or {}
    try:
        out = env.call_tool(tool, args)
        res.tool_calls.append(ToolCall(tool, args, out, True))
        return f"Результат {tool}: {json.dumps(out, ensure_ascii=False)}"
    except Exception as e:  # noqa — даём модели шанс исправиться на неизвестный инструмент/неверные аргументы
        res.tool_calls.append(ToolCall(tool, args, str(e), False))
        return f"Ошибка вызова {tool}: {e}"


class ReferenceReactAgent(Agent):
    """Референсный агентный baseline: ReAct-цикл на фронтир-модели + инструменты песочницы.
    Показывает «что в принципе даёт агентный подход» до запуска ЦАМ 2.0."""
    name = "reference"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def system_prompt(self, env: Environment) -> str:
        return SYSTEM_PROMPT_AGENT.format(tools=_format_tools(env.tool_specs()))

    def run(self, task, env, user, max_turns=8):
        res = RunResult(task_id=task.id, run_idx=0)
        system = self.system_prompt(env)
        opening = user.first_message()
        res.transcript.append(Turn("user", opening))
        history: list[dict[str, str]] = [{"role": "user", "content": opening}]

        for _ in range(max_turns * 2):  # бюджет шагов: несколько вызовов инструментов + диалог
            reply = self.llm.complete(system, history)
            history.append({"role": "assistant", "content": reply})
            action = _parse_action(reply)
            kind = action.get("action")

            if kind == "tool":
                feedback = _apply_tool(env, action, res)
                history.append({"role": "user", "content": feedback})
                continue

            text = str(action.get("text", "")).strip()
            res.transcript.append(Turn("agent", text))
            if kind == "done":
                break
            user_reply = user.reply(text)
            res.transcript.append(Turn("user", user_reply))
            history.append({"role": "user", "content": user_reply})

        res.final_state = env.composite_state()
        return res


class Cam1Adapter(Agent):
    """ЦАМ 1.0 (baseline). Классификаторы + зашитая логика, без вызова наших инструментов,
    поэтому обычно оценивается в JUDGE-режиме (по диалогу/достижению цели)."""
    name = "cam1"

    def __init__(self, endpoint: str | None = None, token: str | None = None):
        self.endpoint = endpoint or os.getenv("CAM1_ENDPOINT", "")
        self.token = token or os.getenv("CAM1_TOKEN", "")

    def run(self, task, env, user, max_turns=8):
        # TODO: вести диалог с API старого ЦАМ:
        #  msg = user.first_message(); пока не конец: resp = POST endpoint {session, msg}; user.reply(resp);
        #  собрать transcript. Состояние песочницы 1.0 обычно НЕ меняет -> reward_mode=JUDGE.
        raise NotImplementedError("Подключите API ЦАМ 1.0 (CAM1_ENDPOINT) и реализуйте диалог.")


class Cam2Adapter(Agent):
    """ЦАМ 2.0 по A2A: шлём Task {intent, context, session_id}, читаем TaskResult,
    инструменты 2.0 перенаправлены на нашу песочницу -> reward_mode=STATE."""
    name = "cam2"

    def __init__(self, endpoint: str | None = None, token: str | None = None):
        self.endpoint = endpoint or os.getenv("CAM2_A2A_ENDPOINT", "")
        self.token = token or os.getenv("CAM2_TOKEN", "")

    def run(self, task, env, user, max_turns=8):
        # TODO: сформировать A2A Task {intent: task.user_goal, context: {...}, session_id};
        #  POST на A2A endpoint; обрабатывать TaskResult {answer, confidence} и промежуточные вызовы;
        #  убедиться, что инструменты 2.0 ходят в нашу Environment (staging).
        raise NotImplementedError("Подключите A2A endpoint ЦАМ 2.0, когда он запустится.")


def build_agent(kind: str, llm: LLMClient, **kw) -> Agent:
    if kind == "demo":
        return DemoAgent(**kw)
    if kind == "reference":
        return ReferenceReactAgent(llm)
    if kind == "cam1":
        return Cam1Adapter()
    if kind == "cam2":
        return Cam2Adapter()
    raise ValueError(f"unknown agent: {kind}")
