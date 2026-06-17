"""Тонкая обёртка над LLM для агента, симулятора пользователя и судьи.
FakeLLM позволяет гонять dry-run без ключей и сети. Большинство вендоров (OpenAI, DeepSeek,
Qwen, GLM, Moonshot, Mistral, Gemini, YandexGPT) дают OpenAI-совместимый API — их покрывает
один клиент OpenAICompatLLM с разным base_url. GigaChat и Anthropic — заглушки с TODO."""
from __future__ import annotations
import os
from time import perf_counter


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


class OpenAICompatLLM(LLMClient):
    """Любой провайдер с OpenAI-совместимым API: OpenAI, DeepSeek, Qwen, GLM, Moonshot,
    Mistral, Gemini, YandexGPT и др. Отличаются только base_url — SDK один (openai),
    импортируется лениво. Необязательные параметры (temperature/max_tokens) не навязываем:
    reasoning-модели их ограничивают — шлём только model+messages (+ явный **kw при нужде)."""
    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        super().__init__()
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _client_or_init(self):
        if self._client is None:
            from openai import OpenAI  # ленивый импорт: нужен только в реальном режиме
            self._client = OpenAI(api_key=self.api_key or None, base_url=self.base_url or None)
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


class AnthropicLLM(LLMClient):  # TODO: реализовать при подключении ключа (свой SDK)
    def __init__(self, model: str, api_key: str):
        super().__init__()
        self.model, self.api_key = model, api_key

    def complete(self, system, messages, **kw):
        # TODO: import anthropic; client.messages.create(model=self.model, system=system, messages=messages,...)
        raise NotImplementedError("Подключите anthropic SDK и реализуйте complete().")


class GigaChatLLM(LLMClient):  # TODO: GigaChat (Сбер) — своя OAuth-авторизация, не OpenAI-совместим из коробки
    def __init__(self, model: str, api_key: str):
        super().__init__()
        self.model, self.api_key = model or "GigaChat", api_key

    def complete(self, system, messages, **kw):
        # TODO: OAuth (POST .../oauth -> access_token на ~30 мин) + POST .../chat/completions с Bearer.
        #  Учесть российский корневой сертификат (Минцифры). Готовый клиент — пакет `gigachat`.
        raise NotImplementedError("Подключите GigaChat (OAuth + пакет gigachat) и реализуйте complete().")


# OpenAI-совместимые провайдеры: (base_url по умолчанию, дефолтная модель).
# base_url переопределяется через LLM_BASE_URL, модель — через LLM_MODEL.
_PROVIDERS: dict[str, tuple[str | None, str]] = {
    "openai":   (None,                                                       "gpt-5.5"),
    "deepseek": ("https://api.deepseek.com",                                 "deepseek-chat"),         # Китай
    "qwen":     ("https://dashscope.aliyuncs.com/compatible-mode/v1",        "qwen-plus"),             # Китай · Alibaba
    "glm":      ("https://open.bigmodel.cn/api/paas/v4",                     "glm-4-plus"),            # Китай · Zhipu
    "moonshot": ("https://api.moonshot.cn/v1",                               "moonshot-v1-8k"),        # Китай · Kimi
    "mistral":  ("https://api.mistral.ai/v1",                                "mistral-large-latest"),  # Франция
    "gemini":   ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.0-flash"),      # Google
    "yandex":   ("https://llm.api.cloud.yandex.net/v1",                      ""),  # Россия; модель: gpt://<folder-id>/yandexgpt/latest
}


def _require_key(key: str, env_fallback: str) -> None:
    if not key and not os.getenv(env_fallback):
        raise SystemExit(
            f"Не задан ключ LLM. Впишите LLM_API_KEY в .env (или {env_fallback} в окружение).\n"
            f"Для прогона без сети используйте --dry-run или LLM_PROVIDER=fake.")


def _make(provider: str, model: str, key: str, base_url: str = "") -> LLMClient:
    if provider == "fake":
        return FakeLLM()
    if provider == "anthropic":
        _require_key(key, "ANTHROPIC_API_KEY")
        return AnthropicLLM(model, key)
    if provider == "gigachat":
        _require_key(key, "GIGACHAT_API_KEY")
        return GigaChatLLM(model, key)
    if provider in _PROVIDERS:
        default_url, default_model = _PROVIDERS[provider]
        _require_key(key, provider.upper() + "_API_KEY")
        return OpenAICompatLLM(model or default_model, key, base_url or default_url)
    allowed = " | ".join(["fake", *_PROVIDERS, "anthropic", "gigachat"])
    raise SystemExit(f"Неизвестный LLM_PROVIDER={provider!r}. Допустимо: {allowed}.\n"
                     f"Любой другой OpenAI-совместимый вендор: LLM_PROVIDER=openai + LLM_BASE_URL=<url>.")


def build_llm() -> LLMClient:
    return _make(os.getenv("LLM_PROVIDER", "fake").lower(), os.getenv("LLM_MODEL", ""),
                 os.getenv("LLM_API_KEY", ""), os.getenv("LLM_BASE_URL", ""))


def build_judge_llm(default: LLMClient) -> LLMClient:
    """Опциональный отдельный судья (LLM_JUDGE_*) — лучше НЕЗАВИСИМЫЙ вендор, чтобы не оценивал
    «сам себя». Если переменные не заданы — та же модель, что у агента/симулятора."""
    if not (os.getenv("LLM_JUDGE_PROVIDER") or os.getenv("LLM_JUDGE_MODEL")):
        return default
    return _make(os.getenv("LLM_JUDGE_PROVIDER", os.getenv("LLM_PROVIDER", "fake")).lower(),
                 os.getenv("LLM_JUDGE_MODEL", ""),
                 os.getenv("LLM_JUDGE_API_KEY", os.getenv("LLM_API_KEY", "")),
                 os.getenv("LLM_JUDGE_BASE_URL", ""))
