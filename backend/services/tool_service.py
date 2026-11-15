from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


class ToolRegistry:
    """Registry for sync or async callable tools used by agents."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        """Register a tool callable under a stable name."""

        if not name:
            raise ValueError("tool name is required")
        if not callable(fn):
            raise TypeError("tool must be callable")
        self._tools[name] = fn

    def get(self, name: str) -> Callable[..., Any] | None:
        """Return a tool by name, or None if missing."""

        return self._tools.get(name)

    def list(self) -> list[str]:
        """Return the registered tool names in sorted order."""

        return sorted(self._tools.keys())

    def unregister(self, name: str) -> None:
        """Remove a tool if it exists."""

        self._tools.pop(name, None)

    def register_module_tools(self, module: Any) -> None:
        """Register public callables from a module using their function names."""

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr_value = getattr(module, attr_name)
            if callable(attr_value) and (
                inspect.isfunction(attr_value) or inspect.iscoroutinefunction(attr_value)
            ):
                self.register(attr_name, attr_value)


_default_registry: ToolRegistry | None = None


def _load_default_tools(registry: ToolRegistry) -> None:
    """Register built-in tool modules on first registry creation."""

    from ..tools import calendar_tools, crm_tools, email_tools, notification_tools, web_search_tools

    for module in (
        calendar_tools,
        crm_tools,
        email_tools,
        notification_tools,
        web_search_tools,
    ):
        registry.register_module_tools(module)


def get_tool_registry() -> ToolRegistry:
    """Return the module-level tool registry singleton."""

    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        _load_default_tools(_default_registry)
    return _default_registry


def register(name: str, fn: Callable[..., Any]) -> None:
    """Register a tool in the default registry."""

    get_tool_registry().register(name, fn)


def get(name: str) -> Callable[..., Any] | None:
    """Look up a tool in the default registry."""

    return get_tool_registry().get(name)
