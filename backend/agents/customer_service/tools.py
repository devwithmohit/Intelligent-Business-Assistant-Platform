from ...services.tool_service import ToolRegistry, get_tool_registry
from ...services.crm_client import create_ticket


def register_tools(registry: ToolRegistry | None = None) -> ToolRegistry:
    active_registry = registry or get_tool_registry()
    active_registry.register("create_ticket", create_ticket)
    return active_registry
