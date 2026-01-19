# app/agents/__init__.py
"""
Agent infrastructure for automated data gathering and enrichment.

Agents use LLM providers with web search to research entities and propose
database updates. Results are returned for human review before committing.

Usage:
    from app.agents import agency_agent
    
    result = agency_agent.execute({'name': 'TriMet'})
    if result.success:
        # Review result.draft, result.diff, result.skipped_fields
        # Then commit if approved
"""

from .base import BaseAgent, AgentResult, LogEntry
from .providers import get_provider, LLMProvider
from .tools import get_tool_registry, register_tool, Tool, ToolResult

# Import agents (this also registers their tools)
from .agency_agent import agency_agent, AgencyAgent

__all__ = [
    # Base classes
    'BaseAgent',
    'AgentResult', 
    'LogEntry',
    
    # Providers
    'get_provider',
    'LLMProvider',
    
    # Tools
    'get_tool_registry',
    'register_tool',
    'Tool',
    'ToolResult',
    
    # Agents
    'agency_agent',
    'AgencyAgent',
]