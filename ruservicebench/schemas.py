"""Схемы данных харнесса. Намеренно на стандартной библиотеке (dataclasses),
чтобы dry-run работал без установки зависимостей. При желании легко заменить на pydantic."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    SINGLE = "single"        # одна услуга в рамках одного домена/Skill-модели
    MULTI = "multi"          # мультидомен: координатор должен задействовать >1 агента
    PROACTIVE = "proactive"  # агент должен проявить инициативу (предложить/сделать сам)


class RewardMode(str, Enum):
    STATE = "state"  # сверка финального состояния песочницы с ожидаемым
    JUDGE = "judge"  # LLM-судья по цели/рубрике (нужно для GovTech 1.0 без инструментов в песочнице)


@dataclass
class Assertion:
    """Проверка для state-режима: значение по dotted-пути в составном состоянии песочницы."""
    path: str            # напр. "jkh.accounts.123.meters.cold"
    equals: Any


@dataclass
class Task:
    id: str
    title: str
    domains: list[str]                       # ["jkh"], ["edu","mfc"] ...
    type: TaskType
    reward_mode: RewardMode
    user_goal: str                           # цель пользователя (на русском)
    user_persona: str = "вежливый житель Москвы"
    user_values: dict[str, Any] = field(default_factory=dict)   # что пользователь раскроет по запросу
    initial_state: dict[str, Any] = field(default_factory=dict)  # стартовое состояние по доменам
    expected: list[Assertion] = field(default_factory=list)      # для STATE
    rubric: str = ""                                             # для JUDGE
    demo_solution: list[dict[str, Any]] = field(default_factory=list)  # для dry-run DemoAgent

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Task":
        try:
            task = Task(
                id=d["id"], title=d["title"], domains=d["domains"],
                type=TaskType(d["type"]), reward_mode=RewardMode(d["reward_mode"]),
                user_goal=d["user_goal"], user_persona=d.get("user_persona", "вежливый житель Москвы"),
                user_values=d.get("user_values", {}), initial_state=d.get("initial_state", {}),
                expected=[Assertion(**a) for a in d.get("expected", [])],
                rubric=d.get("rubric", ""), demo_solution=d.get("demo_solution", []),
            )
        except KeyError as e:
            raise ValueError(f"задача {d.get('id', '?')!r}: отсутствует обязательное поле {e}") from None
        validate_task(task)
        return task


def validate_task(t: Task) -> None:
    """Валидация задачи на границе (загрузка из JSON): понятные ошибки для авторов-предметников."""
    where = f"задача {t.id!r}"
    if not t.id or not t.title:
        raise ValueError(f"{where}: пустые id или title")
    if not t.domains:
        raise ValueError(f"{where}: не указаны домены")
    if t.reward_mode == RewardMode.STATE and not t.expected:
        raise ValueError(f"{where}: reward_mode=state требует непустой expected")
    if t.reward_mode == RewardMode.JUDGE and not t.rubric:
        raise ValueError(f"{where}: reward_mode=judge требует непустой rubric")
    for a in t.expected:
        head = a.path.split(".")[0]
        if head not in t.domains:
            raise ValueError(f"{where}: путь assertion {a.path!r} вне доменов задачи {t.domains}")
    for i, step in enumerate(t.demo_solution):
        if "tool" not in step and "say" not in step:
            raise ValueError(f"{where}: demo_solution[{i}] должен содержать 'tool' или 'say'")


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any]
    result: Any = None
    ok: bool = True


@dataclass
class Turn:
    role: str   # "user" | "agent"
    text: str


@dataclass
class RunResult:
    task_id: str
    run_idx: int
    success: bool = False
    transcript: list[Turn] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_state: dict[str, Any] = field(default_factory=dict)
    judge_score: float | None = None
    detail: str = ""
    error: str | None = None
    failure_class: str = ""              # таксономия провала (заполняется при success=False)
    llm_calls: int = 0                   # вызовов LLM за прогон (агент + пользователь + судья)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0               # суммарная задержка LLM-вызовов, сек

    def to_row(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "run_idx": self.run_idx,
            "success": int(self.success), "n_tool_calls": len(self.tool_calls),
            "judge_score": self.judge_score if self.judge_score is not None else "",
            "failure_class": self.failure_class,
            "llm_calls": self.llm_calls, "tokens": self.prompt_tokens + self.completion_tokens,
            "latency_s": round(self.latency_s, 2),
            "detail": self.detail, "error": self.error or "",
        }
