from ...services.tool_service import ToolRegistry, get_tool_registry


def register_tools(registry: ToolRegistry | None = None) -> ToolRegistry:
    return registry or get_tool_registry()
