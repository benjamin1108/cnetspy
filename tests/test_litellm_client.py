#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LiteLLM 客户端适配测试。"""

from src.analyzers import gemini_client as gemini_client_module
from src.analyzers.gemini_client import GeminiClient
from src.api.routes.chat import _generate_with_gemini


class FakeLiteLLM:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or ['{"ok": true}'])

    def completion(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return {"choices": [{"message": {"content": response}}]}


def _base_config(**overrides):
    config = {
        "provider": "dashscope",
        "model_name": "qwen3.7-max",
        "api_key_env": "DASHSCOPE_API_KEY",
        "generation": {
            "temperature": 0.2,
            "top_p": 0.8,
            "max_output_tokens": 123,
        },
        "rate_limit": {
            "interval": 0,
            "max_retries": 1,
        },
    }
    config.update(overrides)
    return config


def test_dashscope_model_name_is_normalized_and_completion_is_called(monkeypatch):
    fake_litellm = FakeLiteLLM(["dashscope ok"])
    monkeypatch.setattr(gemini_client_module, "litellm", fake_litellm)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    client = GeminiClient(_base_config())
    result = client.generate_text("hello")

    assert result == "dashscope ok"
    assert client.model_name == "dashscope/qwen3.7-max"
    assert fake_litellm.calls[0]["model"] == "dashscope/qwen3.7-max"
    assert fake_litellm.calls[0]["messages"] == [{"role": "user", "content": "hello"}]
    assert fake_litellm.calls[0]["temperature"] == 0.2
    assert fake_litellm.calls[0]["max_tokens"] == 123


def test_gemini_model_name_is_normalized(monkeypatch):
    fake_litellm = FakeLiteLLM(["gemini ok"])
    monkeypatch.setattr(gemini_client_module, "litellm", fake_litellm)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")

    client = GeminiClient(
        _base_config(
            provider="gemini",
            model_name="gemini-3.5-flash",
            api_key_env="GEMINI_API_KEY",
        )
    )

    assert client.model_name == "gemini/gemini-3.5-flash"


def test_response_format_falls_back_when_provider_rejects_schema(monkeypatch):
    fake_litellm = FakeLiteLLM(
        [
            RuntimeError("unsupported parameter: response_format"),
            '{"title_translated":"标题"}',
        ]
    )
    monkeypatch.setattr(gemini_client_module, "litellm", fake_litellm)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    client = GeminiClient(_base_config(rate_limit={"interval": 0, "max_retries": 2}))
    result = client.generate_content("analyze")

    assert result == '{"title_translated":"标题"}'
    assert "response_format" in fake_litellm.calls[0]
    assert "response_format" not in fake_litellm.calls[1]


def test_chat_route_uses_litellm_message_interface():
    class ChatClient:
        def __init__(self):
            self.messages = None

        def complete_messages(self, messages, **kwargs):
            self.messages = messages
            return "ok"

    client = ChatClient()

    result = _generate_with_gemini(
        client,
        "ignored-model",
        [{"role": "user", "parts": [{"text": "hello"}]}],
        system_instruction="system",
        temperature=0.4,
        max_output_tokens=99,
    )

    assert result == "ok"
    assert client.messages == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
    ]
