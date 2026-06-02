import pytest
from mcp.types import CallToolRequest, ListToolsRequest

from manuals_app.mcp_server import create_app


class TestCreateApp:
    def test_returns_server(self):
        app = create_app()
        assert app.name == "diy-manuals"

    @pytest.mark.asyncio
    async def test_list_tools_returns_tool(self):
        app = create_app()
        req = ListToolsRequest(method="tools/list", params={})
        result = await app.request_handlers[ListToolsRequest](req)
        tools = result.root.tools
        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "search_manuals"
        assert "query" in tool.inputSchema["required"]
        assert "query" in tool.inputSchema["properties"]
        assert "category" in tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_call_unknown_tool_returns_error(self):
        app = create_app()
        req = CallToolRequest(method="tools/call", params={"name": "bad_tool", "arguments": {}})
        result = await app.request_handlers[CallToolRequest](req)
        assert result.root.isError is True
        assert "bad_tool" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_call_tool_no_results(self, populated_db, monkeypatch):
        app = create_app()
        monkeypatch.setenv("DATABASE_PATH", str(populated_db))
        req = CallToolRequest(
            method="tools/call",
            params={"name": "search_manuals", "arguments": {"query": "xyznonexistent"}},
        )
        result = await app.request_handlers[CallToolRequest](req)
        assert result.root.isError is False
        assert "couldn't find" in result.root.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_call_tool_search(self, populated_db, monkeypatch):
        app = create_app()
        monkeypatch.setenv("DATABASE_PATH", str(populated_db))
        req = CallToolRequest(
            method="tools/call",
            params={"name": "search_manuals", "arguments": {"query": "oil"}},
        )
        result = await app.request_handlers[CallToolRequest](req)
        assert result.root.isError is False
        assert len(result.root.content) == 1
        assert "5W-30" in result.root.content[0].text
        assert result.root.content[0].type == "text"
