from ...services.tool_service import ToolRegistry, get_tool_registry
from ...tools.crm_tools import list_contacts
from ...tools.web_search_tools import search_web


def register_tools(registry: ToolRegistry | None = None) -> ToolRegistry:
    active_registry = registry or get_tool_registry()
    active_registry.register("search_web", search_web)
    active_registry.register("list_contacts", list_contacts)
    return active_registry
