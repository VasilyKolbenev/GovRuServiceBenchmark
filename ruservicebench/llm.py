"""Тонкая обёртка над LLM для симулятора пользователя и судьи.
FakeLLM позволяет гонять dry-run без ключей и сети. Реальные провайдеры — заглушки с TODO."""
from __future__ import annotations
import os
from time import perf_counter
from typing import Any


class LLMClient:
    """Базовый клиент. Ведёт счётчики использования (вызовы/токены/задержка),
    чтобы раннер считал стоимость и скорость каждого прогона."""
    def __init__(self) -> None:
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.latency_s = 0.0

    def complete(self, system: str, messages: list[dict[str, str]], **kw) -> str:
        raise NotImplementedError

    def _record(self, t0: float, prompt_tokens: int, completion_tokens: int) -> None:
        self.calls += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.latency_s += perf_counter() - t0

    def usage_snapshot(self) -> dict[str, float]:
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "latency_s": self.latency_s}


class FakeLLM(LLMClient):
    """Детерминированная заглушка: не «думает», возвращает безопасные ответы.
    Нужна только чтобы пайплайн исполнялся в dry-run без внешних вызовов."""
    def complete(self, system: str, messages: list[dict[str, str]], **kw) -> str:
        t0 = perf_counter()
        last = messages[-1]["content"] if messages else ""
        self._record(t0, 0, 0)
        return f"[FAKE-LLM] (эхо) {last[:120]}"


class AnthropicLLM(LLMClient):  # TODO: реализовать при подключении ключа
    def __init__(self, model: str, api_key: str):
        super().__init__()
        self.model, self.api_key = model, api_key

    def complete(self, system, messages, **kw):
        # TODO: import anthropic; client.messages.create(model=self.model, system=system, messages=messages,...)
        raise NotImplementedError("Подключите anthropic SDK и реализуйте complete().")


class OpenAILLM(LLMClient):
    """OpenAI Chat Completions. SDK импортируется лениво — ядро и dry-run работают без него.
    Необязательные параметры (temperature/max_tokens) не навязываем: GPT-5-семейство
    (reasoning) их ограничивает, поэтому шлём только model+messages (+ явный **kw при нужде)."""
    def __init__(self, model: str, api_key: str):
        super().__init__()
        self.model = model
        self.api_key = api_key
        self._client = None

    def _client_or_init(self):
        if self._client is None:
            from openai import OpenAI  # ленивый импорт: нужен только в реальном режиме
            self._client = OpenAI(api_key=self.api_key or None)
        return self._client

    def complete(self, system: str, messages: list[dict[str, str]], **kw) -> str:
        client = self._client_or_init()
        full = [{"role": "system", "content": system}, *messages]
        t0 = perf_counter()
        resp = client.chat.completions.create(model=self.model, messages=full, **kw)
        usage = getattr(resp, "usage", None)
        self._record(t0, getattr(usage, "prompt_tokens", 0) or 0,
                     getattr(usage, "completion_tokens", 0) or 0)
        return (resp.choices[0].message.content or "").strip()


def _require_key(key: str, env_fallback: str) -> None:
    if not key and not os.getenv(env_fallback):
        raise SystemExit(
            f"Не задан ключ LLM. Впишите LLM_API_KEY в .env (или {env_fallback} в окружение).\n"
            f"Для прогона без сети используйте --dry-run или LLM_PROVIDER=fake.")


def _make(provider: str, model: str, key: str) -> LLMClient:
    if provider == "fake":
        return FakeLLM()
    if provider == "anthropic":
        _require_key(key, "ANTHROPIC_API_KEY")
        return AnthropicLLM(model or "claude-opus-4-8", key)
    if provider == "openai":
        _require_key(key, "OPENAI_API_KEY")
        return OpenAILLM(model or "gpt-5.5", key)
    raise SystemExit(f"Неизвестный LLM_PROVIDER={provider!r}. Допустимо: fake | anthropic | openai.")


def build_llm() -> LLMClient:
    return _make(os.getenv("LLM_PROVIDER", "fake").lower(),
                 os.getenv("LLM_MODEL", ""), os.getenv("LLM_API_KEY", ""))


def build_judge_llm(default: LLMClient) -> LLMClient:
    """Опциональная отдельная модель судьи (LLM_JUDGE_*), чтобы судья не оценивал «сам себя».
    Если переменные не заданы — используется та же модель, что и для агента/симулятора."""
    if not (os.getenv("LLM_JUDGE_PROVIDER") or os.getenv("LLM_JUDGE_MODEL")):
        return default
    return _make(os.getenv("LLM_JUDGE_PROVIDER", os.getenv("LLM_PROVIDER", "fake")).lower(),
                 os.getenv("LLM_JUDGE_MODEL", ""),
                 os.getenv("LLM_JUDGE_API_KEY", os.getenv("LLM_API_KEY", "")))
