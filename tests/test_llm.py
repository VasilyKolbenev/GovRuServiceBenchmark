"""Тесты фабрики LLM-клиентов: мульти-вендор, переключение, base_url (без сети)."""
import unittest
from ruservicebench.llm import _make, FakeLLM, OpenAICompatLLM, _PROVIDERS


class TestLLMFactory(unittest.TestCase):
    def test_fake_provider(self):
        self.assertIsInstance(_make("fake", "", ""), FakeLLM)

    def test_openai_compatible_providers_build(self):
        for provider, (base_url, default_model) in _PROVIDERS.items():
            client = _make(provider, "", "test-key")
            self.assertIsInstance(client, OpenAICompatLLM)
            self.assertEqual(client.base_url, base_url)
            if default_model:
                self.assertEqual(client.model, default_model)

    def test_explicit_model_overrides_default(self):
        client = _make("deepseek", "my-model", "k")
        self.assertEqual(client.model, "my-model")

    def test_base_url_override(self):
        client = _make("deepseek", "m", "k", base_url="https://custom/v1")
        self.assertEqual(client.base_url, "https://custom/v1")

    def test_unknown_provider_exits(self):
        with self.assertRaises(SystemExit):
            _make("nonexistent", "", "k")


if __name__ == "__main__":
    unittest.main()
