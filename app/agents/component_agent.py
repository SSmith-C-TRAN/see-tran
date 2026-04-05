# app/agents/component_agent.py
"""
Component agent — Phase 2, not yet implemented.
"""

from .utils import AgentResult


def run(component_id: int, *, dry_run: bool = False) -> AgentResult:
    """Research a component by ID. Not yet implemented."""
    return AgentResult(
        success=False,
        error='component_agent is not yet implemented (Phase 2)',
    )
