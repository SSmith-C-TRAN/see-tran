# app/agents/tools/__init__.py
"""
Agent tools - reusable capabilities for agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolContext:
    """Context passed to tools during execution."""
    params: dict
    provider_name: str = 'anthropic'
    model: str | None = None


@dataclass 
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: dict = field(default_factory=dict)
    confidence: float = 0.0
    logs: list[str] = field(default_factory=list)
    error: str | None = None


class Tool(ABC):
    """Base protocol for agent tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool identifier for logging."""
        pass
    
    @abstractmethod
    def execute(self, context: ToolContext) -> ToolResult:
        """Execute the tool with given context."""
        pass


class ToolRegistry:
    """Registry for available tools."""
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def execute(self, name: str, context: ToolContext) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {name}",
            )
        return tool.execute(context)


# Global tool registry
_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry


def register_tool(tool: Tool) -> None:
    """Register a tool in the global registry."""
    _registry.register(tool)