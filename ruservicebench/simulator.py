"""Симулятор пользователя: играет русскоязычного жителя с целью.
В dry-run работает по скрипту (без LLM). В реальном режиме — LLM с системным промптом ниже,
раскрывает информацию по чуть-чуть (как в tau-bench), не выдаёт всё сразу."""
from __future__ import annotations
from typing import Any
from .llm import LLMClient
from .schemas import Task

SYSTEM_PROMPT_TEMPLATE = """Ты играешь роль пользователя — {persona}.
Твоя цель: {goal}
Известные тебе данные (раскрывай ТОЛЬКО когда агент конкретно спросит, по одному, не вываливай всё сразу):
{values}
Правила:
- Пиши коротко и естественно, на русском, как обычный человек.
- Не подсказывай агенту, какие инструменты вызывать.
- Если агент решил задачу — поблагодари и заверши. Если ушёл не туда — мягко поправь.
- Не выходи из роли пользователя."""


class UserSimulator:
    def __init__(self, task: Task, llm: LLMClient, scripted: bool = False):
        self.task = task
        self.llm = llm
        self.scripted = scripted
        # История с точки зрения симулятора: реплики агента — role "user", свои ответы — "assistant".
        self._history: list[dict[str, str]] = []

    def system_prompt(self) -> str:
        vals = "\n".join(f"- {k}: {v}" for k, v in self.task.user_values.items()) or "- (нет дополнительных данных)"
        return SYSTEM_PROMPT_TEMPLATE.format(persona=self.task.user_persona, goal=self.task.user_goal, values=vals)

    def first_message(self) -> str:
        msg = self.task.user_goal
        self._history.append({"role": "assistant", "content": msg})
        return msg

    def reply(self, agent_message: str) -> str:
        """Ответ пользователя на реплику агента (LLM-режим — частичное раскрытие данных по промпту)."""
        if self.scripted:
            return self._scripted_reply(agent_message)
        self._history.append({"role": "user", "content": agent_message})
        answer = self.llm.complete(self.system_prompt(), self._history)
        self._history.append({"role": "assistant", "content": answer})
        return answer

    def _scripted_reply(self, agent_message: str) -> str:
        """Скриптовый ответ для dry-run: отдаём запрошенные значения, иначе короткое подтверждение."""
        low = agent_message.lower()
        for k, v in self.task.user_values.items():
            if k.lower() in low or any(w in low for w in str(k).lower().split("_")):
                return str(v)
        return "Да, всё верно, спасибо."
