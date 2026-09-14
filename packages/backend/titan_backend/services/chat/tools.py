from collections.abc import Callable
from typing import Any, NamedTuple

from titan_backend.core.logging import logger


class ToolDefinition(NamedTuple):
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]


class ToolRegistry:
    """Registry for AI Assistant function calling and external action execution."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def get_litellm_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        tool = self._tools[name]
        logger.info("executing_agent_tool", tool_name=name)
        result = tool.handler(**arguments)
        if hasattr(result, "__await__"):
            return await result
        return result


tool_registry = ToolRegistry()
