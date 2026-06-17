"""Оценка одного прогона. Два режима награды:
  STATE — сверка финального состояния песочницы с task.expected (для референс-агента и GovTech 2.0);
  JUDGE — оценка по цели/рубрике (для GovTech 1.0 без инструментов; и для проактивности).
В dry-run судья работает по простой эвристике (без LLM)."""
from __future__ import annotations
from typing import Any
from .schemas import Task, RunResult, RewardMode
from .llm import LLMClient, FakeLLM


def _resolve(state: dict[str, Any], path: str) -> Any:
    cur: Any = state
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _verdict(out: str) -> bool:
    """Надёжный разбор вердикта судьи: ждём PASS/FAIL первой строкой, иначе — запасной разбор."""
    upper = out.upper()
    first = next((ln.strip() for ln in upper.splitlines() if ln.strip()), "")
    if first.startswith("PASS"):
        return True
    if first.startswith("FAIL"):
        return False
    return upper.rfind("PASS") > upper.rfind("FAIL")  # последнее упоминание; оба отсутствуют -> FAIL


def evaluate_state(task: Task, run: RunResult) -> tuple[bool, str]:
    fails = []
    for a in task.expected:
        got = _resolve(run.final_state, a.path)
        if got != a.equals:
            fails.append(f"{a.path}: ожидали {a.equals!r}, получили {got!r}")
    return (len(fails) == 0, "OK" if not fails else "; ".join(fails))


def evaluate_judge(task: Task, run: RunResult, llm: LLMClient) -> tuple[bool, float, str]:
    transcript = "\n".join(f"{t.role}: {t.text}" for t in run.transcript)
    if isinstance(llm, FakeLLM):
        # Эвристика для dry-run: цель «достигнута», если в диалоге агента есть признак действия/инициативы.
        agent_txt = " ".join(t.text.lower() for t in run.transcript if t.role == "agent")
        keywords = ["оформил", "записал", "передал", "оплат", "предлаг", "напомин", "готово", "заявк"]
        ok = any(k in agent_txt for k in keywords)
        return ok, 1.0 if ok else 0.0, "[fake-judge] эвристика по ключевым словам"
    # Реальный режим:
    system = ("Ты — строгий оценщик качества диалога агента госуслуг. "
              "Первой строкой выведи РОВНО одно слово: PASS или FAIL. Затем краткое обоснование.")
    prompt = (f"Цель пользователя: {task.user_goal}\nРубрика: {task.rubric or 'достигнута ли цель корректно и без вреда'}\n\n"
              f"Диалог:\n{transcript}\n\nВердикт:")
    out = llm.complete(system, [{"role": "user", "content": prompt}])
    ok = _verdict(out)
    return ok, 1.0 if ok else 0.0, out[:300]


def evaluate(task: Task, run: RunResult, llm: LLMClient) -> RunResult:
    if task.reward_mode == RewardMode.STATE:
        ok, detail = evaluate_state(task, run)
        run.success, run.detail = ok, detail
    else:
        ok, score, detail = evaluate_judge(task, run, llm)
        run.success, run.judge_score, run.detail = ok, score, detail
    return run


def classify_failure(task: Task, run: RunResult) -> str:
    """Грубая таксономия причины провала — для разбора «почему агент сыпется».
    Категории: exception | tool_error | judge_fail | no_action | wrong_outcome."""
    if run.error:
        return "exception"
    if any(not tc.ok for tc in run.tool_calls):
        return "tool_error"            # неверный инструмент или аргументы
    if task.reward_mode == RewardMode.JUDGE:
        return "judge_fail"            # судья не зачёл цель/проактивность
    if not run.tool_calls:
        return "no_action"             # ничего не сделал в песочнице
    return "wrong_outcome"             # звал инструменты, но финальное состояние не сошлось
