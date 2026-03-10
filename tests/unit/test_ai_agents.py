"""Tests for the AI Agents plugin — tools and agent loop."""

import sys
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from tests.unit.conftest_ai import load_all_ai_plugins

load_all_ai_plugins()

from fastcms_plugin.ai_agents.tools import (
    TOOL_DEFINITIONS,
    WRITE_TOOLS,
    execute_tool,
)
from fastcms_plugin.ai_core.providers import (
    CompletionResponse,
    ToolCall,
    ToolDefinition,
)

# Force-import agent submodule
from fastcms_plugin.ai_agents import agent as _agent_mod


# ---------------------------------------------------------------------------
# Tool definitions tests
# ---------------------------------------------------------------------------

class TestToolDefinitions:
    def test_all_tools_defined(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "list_collections" in names
        assert "query_records" in names
        assert "get_record" in names
        assert "create_record" in names
        assert "update_record" in names
        assert "search_records" in names
        assert "semantic_search" in names

    def test_write_tools_identified(self):
        assert "create_record" in WRITE_TOOLS
        assert "update_record" in WRITE_TOOLS
        assert "list_collections" not in WRITE_TOOLS
        assert "query_records" not in WRITE_TOOLS

    def test_tool_schemas_valid(self):
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert isinstance(tool["parameters"], dict)

    def test_required_fields(self):
        for tool in TOOL_DEFINITIONS:
            params = tool["parameters"]
            assert "type" in params
            assert params["type"] == "object"


# ---------------------------------------------------------------------------
# Tool execution tests
# ---------------------------------------------------------------------------

class TestToolExecution:
    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await execute_tool("nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_list_collections(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("posts", "base", '{"fields": []}'),
            ("users", "auth", '{"fields": []}'),
        ]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.db.session.AsyncSessionLocal",
            return_value=mock_db,
        ):
            result = await execute_tool("list_collections", {})
            assert "collections" in result
            assert len(result["collections"]) == 2
            assert result["collections"][0]["name"] == "posts"

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        with patch(
            "app.db.session.AsyncSessionLocal",
            side_effect=Exception("DB connection failed"),
        ):
            result = await execute_tool("list_collections", {})
            assert "error" in result


# ---------------------------------------------------------------------------
# Agent loop tests
# ---------------------------------------------------------------------------

class TestAgentLoop:
    @pytest.mark.asyncio
    async def test_simple_agent_run(self):
        mock_provider = AsyncMock()
        mock_provider.default_model = "test-model"
        mock_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                content="There are 2 collections: posts and users.",
                model="test-model",
                usage={},
                tool_calls=[],
                finish_reason="stop",
            )
        )

        with patch(
            "fastcms_plugin.ai_core.providers.get_provider",
            return_value=mock_provider,
        ):
            result = await _agent_mod.run_agent("How many collections exist?")
            assert "collections" in result.answer.lower()
            assert result.model == "test-model"
            assert any(s.type == "answer" for s in result.steps)

    @pytest.mark.asyncio
    async def test_agent_with_tool_call(self):
        tool_response = CompletionResponse(
            content="",
            model="test-model",
            usage={},
            tool_calls=[ToolCall(name="list_collections", arguments={})],
            finish_reason="tool_calls",
        )
        final_response = CompletionResponse(
            content="Found 1 collection: articles.",
            model="test-model",
            usage={},
            tool_calls=[],
            finish_reason="stop",
        )

        mock_provider = AsyncMock()
        mock_provider.default_model = "test-model"
        mock_provider.complete = AsyncMock(
            side_effect=[tool_response, final_response]
        )

        mock_tool_result = {"collections": [{"name": "articles", "type": "base"}]}

        with (
            patch(
                "fastcms_plugin.ai_core.providers.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "fastcms_plugin.ai_agents.agent.execute_tool",
                return_value=mock_tool_result,
            ),
        ):
            result = await _agent_mod.run_agent("List collections")
            assert "articles" in result.answer
            step_types = [s.type for s in result.steps]
            assert "tool_call" in step_types
            assert "tool_result" in step_types
            assert "answer" in step_types

    @pytest.mark.asyncio
    async def test_agent_respects_max_iterations(self):
        infinite_response = CompletionResponse(
            content="",
            model="test-model",
            usage={},
            tool_calls=[ToolCall(name="list_collections", arguments={})],
            finish_reason="tool_calls",
        )

        mock_provider = AsyncMock()
        mock_provider.default_model = "test-model"
        mock_provider.complete = AsyncMock(return_value=infinite_response)

        with (
            patch(
                "fastcms_plugin.ai_core.providers.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "fastcms_plugin.ai_agents.agent.execute_tool",
                return_value={"collections": []},
            ),
        ):
            result = await _agent_mod.run_agent("Loop forever")
            assert (
                "maximum" in result.answer.lower()
                or "incomplete" in result.answer.lower()
            )

    @pytest.mark.asyncio
    async def test_agent_write_tools_disabled_by_default(self):
        mock_provider = AsyncMock()
        mock_provider.default_model = "test-model"
        mock_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                content="Done.", model="test-model", usage={}, tool_calls=[]
            )
        )

        with patch(
            "fastcms_plugin.ai_core.providers.get_provider",
            return_value=mock_provider,
        ):
            await _agent_mod.run_agent("Create a record")
            call_args = mock_provider.complete.call_args
            tools = call_args.kwargs.get("tools", [])
            if tools:
                tool_names = [t.name for t in tools]
                assert "create_record" not in tool_names
                assert "update_record" not in tool_names

    @pytest.mark.asyncio
    async def test_stream_agent(self):
        mock_provider = AsyncMock()
        mock_provider.default_model = "test-model"
        mock_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                content="Streamed answer.",
                model="test-model",
                usage={},
                tool_calls=[],
            )
        )

        with patch(
            "fastcms_plugin.ai_core.providers.get_provider",
            return_value=mock_provider,
        ):
            steps = []
            async for step in _agent_mod.stream_agent("Simple question"):
                steps.append(step)
            assert len(steps) == 1
            assert steps[0].type == "answer"
            assert steps[0].content == "Streamed answer."
