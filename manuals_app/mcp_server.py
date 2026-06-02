import asyncio
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from manuals_app.db import MAX_QUERY_LENGTH, get_database_path
from manuals_app.search import format_context, search_manuals

logger = logging.getLogger(__name__)


def create_app() -> Server:
    app = Server("diy-manuals")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_manuals",
                description="Search indexed owner's manuals for relevant content",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query",
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional category filter (e.g. Automotive, Appliances)",
                        },
                    },
                    "required": ["query"],
                },
            )
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name != "search_manuals":
            raise ValueError(f"Unknown tool: {name}")

        query_raw = arguments.get("query", "")
        query = query_raw[:MAX_QUERY_LENGTH]
        category = arguments.get("category", None)

        try:
            db_path = get_database_path()
            results = await asyncio.to_thread(
                search_manuals, db_path, query, category=category,
            )
        except Exception:
            logger.exception("Search failed")
            return [
                TextContent(
                    type="text",
                    text="Search failed due to an internal error.",
                )
            ]

        if not results:
            return [
                TextContent(
                    type="text",
                    text="I couldn't find relevant information in your manuals.",
                )
            ]

        context = format_context(results)
        return [TextContent(type="text", text=context)]

    return app


async def main():
    app = create_app()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
