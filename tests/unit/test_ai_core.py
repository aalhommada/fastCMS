"""Tests for the AI Core plugin — providers, routes, configuration."""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from tests.unit.conftest_ai import load_all_ai_plugins

load_all_ai_plugins()

from fastcms_plugin.ai_core.providers import (
    AIProvider,
    AnthropicProvider,
    CompletionResponse,
    EmbeddingResponse,
    OllamaProvider,
    OpenAIProvider,
    ProviderError,
    ToolCall,
    ToolDefinition,
    get_provider,
    get_embed_provider,
    init_embed_provider,
    init_provider,
    is_configured,
    list_providers,
    reset,
)


# ---------------------------------------------------------------------------
# Provider registry tests
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    def setup_method(self):
        reset()

    def test_list_providers(self):
        providers = list_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers

    def test_not_configured_initially(self):
        assert is_configured() is False

    def test_get_provider_when_not_configured(self):
        with pytest.raises(ProviderError, match="No AI provider configured"):
            get_provider()

    def test_init_provider_openai(self):
        provider = init_provider("openai", "test-key")
        assert isinstance(provider, OpenAIProvider)
        assert is_configured() is True
        assert get_provider() is provider

    def test_init_provider_anthropic(self):
        provider = init_provider("anthropic", "test-key")
        assert isinstance(provider, AnthropicProvider)
        assert provider.default_model == "claude-sonnet-4-20250514"

    def test_init_provider_ollama(self):
        provider = init_provider("ollama", "")
        assert isinstance(provider, OllamaProvider)
        assert provider.default_model == "llama3.1:8b"

    def test_init_provider_custom_model(self):
        provider = init_provider("openai", "key", model="gpt-4o")
        assert provider.default_model == "gpt-4o"

    def test_init_provider_custom_base_url(self):
        provider = init_provider("openai", "key", base_url="https://custom.api.com/v1")
        assert provider.base_url == "https://custom.api.com/v1"

    def test_init_provider_unknown(self):
        with pytest.raises(ProviderError, match="Unknown provider"):
            init_provider("unknown", "key")

    def test_embed_provider_separate(self):
        init_provider("anthropic", "anthropic-key")
        init_embed_provider("openai", "openai-key")
        # Main provider is Anthropic
        assert isinstance(get_provider(), AnthropicProvider)
        # Embed provider is OpenAI
        assert isinstance(get_embed_provider(), OpenAIProvider)

    def test_embed_provider_falls_back_to_main(self):
        reset()
        init_provider("openai", "key")
        assert get_embed_provider() is get_provider()

    def test_reset(self):
        init_provider("openai", "key")
        assert is_configured() is True
        reset()
        assert is_configured() is False


# ---------------------------------------------------------------------------
# OpenAI provider tests
# ---------------------------------------------------------------------------

class TestOpenAIProvider:
    @pytest.fixture
    def provider(self):
        return OpenAIProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_complete(self, provider):
        mock_response = httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": "Hello!", "role": "assistant"},
                        "finish_reason": "stop",
                    }
                ],
                "model": "gpt-4o-mini",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
        with patch.object(provider, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = client

            result = await provider.complete(
                [{"role": "user", "content": "Hi"}]
            )
            assert result.content == "Hello!"
            assert result.model == "gpt-4o-mini"
            assert result.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, provider):
        mock_response = httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": '{"city": "London"}',
                                    }
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "model": "gpt-4o-mini",
                "usage": {},
            },
        )
        with patch.object(provider, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = client

            result = await provider.complete(
                [{"role": "user", "content": "Weather?"}],
                tools=[
                    ToolDefinition(
                        name="get_weather",
                        description="Get weather",
                        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
                    )
                ],
            )
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "get_weather"
            assert result.tool_calls[0].arguments == {"city": "London"}

    @pytest.mark.asyncio
    async def test_complete_error(self, provider):
        mock_response = httpx.Response(401, text="Unauthorized")
        with patch.object(provider, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = client

            with pytest.raises(ProviderError, match="OpenAI error 401"):
                await provider.complete([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_embed(self, provider):
        mock_response = httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [0.1, 0.2, 0.3], "index": 0},
                    {"embedding": [0.4, 0.5, 0.6], "index": 1},
                ],
                "model": "text-embedding-3-small",
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        )
        with patch.object(provider, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = client

            result = await provider.embed(["hello", "world"])
            assert len(result.embeddings) == 2
            assert result.embeddings[0] == [0.1, 0.2, 0.3]
            assert result.model == "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Anthropic provider tests
# ---------------------------------------------------------------------------

class TestAnthropicProvider:
    @pytest.fixture
    def provider(self):
        return AnthropicProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_complete(self, provider):
        mock_response = httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "Hello!"}],
                "model": "claude-sonnet-4-20250514",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "stop_reason": "end_turn",
            },
        )
        with patch.object(provider, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = client

            result = await provider.complete(
                [
                    {"role": "system", "content": "Be helpful"},
                    {"role": "user", "content": "Hi"},
                ]
            )
            assert result.content == "Hello!"
            # Verify system was extracted from messages
            call_args = client.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert payload["system"] == "Be helpful"
            assert all(m["role"] != "system" for m in payload["messages"])

    @pytest.mark.asyncio
    async def test_complete_with_tool_use(self, provider):
        mock_response = httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "Let me check."},
                    {"type": "tool_use", "name": "search", "input": {"q": "test"}},
                ],
                "model": "claude-sonnet-4-20250514",
                "usage": {},
                "stop_reason": "tool_use",
            },
        )
        with patch.object(provider, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = client

            result = await provider.complete(
                [{"role": "user", "content": "Search"}],
                tools=[
                    ToolDefinition(name="search", description="Search", parameters={})
                ],
            )
            assert result.content == "Let me check."
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "search"

    @pytest.mark.asyncio
    async def test_embed_not_supported(self, provider):
        with pytest.raises(ProviderError, match="does not provide an embedding API"):
            await provider.embed(["test"])


# ---------------------------------------------------------------------------
# Ollama provider tests
# ---------------------------------------------------------------------------

class TestOllamaProvider:
    @pytest.fixture
    def provider(self):
        return OllamaProvider()

    @pytest.mark.asyncio
    async def test_complete(self, provider):
        mock_response = httpx.Response(
            200,
            json={
                "message": {"content": "Hello!", "role": "assistant"},
                "model": "llama3.1:8b",
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )
        with patch.object(provider, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = client

            result = await provider.complete(
                [{"role": "user", "content": "Hi"}]
            )
            assert result.content == "Hello!"
            assert result.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_embed(self, provider):
        mock_response = httpx.Response(
            200,
            json={
                "embeddings": [[0.1, 0.2], [0.3, 0.4]],
                "model": "nomic-embed-text",
            },
        )
        with patch.object(provider, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = client

            result = await provider.embed(["a", "b"])
            assert len(result.embeddings) == 2
            assert result.model == "nomic-embed-text"

    def test_provider_name(self, provider):
        assert provider.provider_name == "ollama"

    def test_no_api_key_needed(self):
        provider = OllamaProvider()
        assert provider.api_key == ""
