# app/agents/__init__.py
"""
AI research agents for automated data gathering and enrichment.

Each agent is a standalone module with a `run(record_id, *, dry_run)` function.
Results are returned as AgentResult for human review before committing.

Usage:
    from app.agents.agency_agent import run as run_agency_agent
    result = run_agency_agent(agency_id=42)
    if result.success:
        # review result.draft, result.diff
        # commit if approved

CLI:
    flask agent run agency --id 42
    flask agent run vendor --name "Cubic Transportation Systems"
    flask agent run agency --all --dry-run
"""

from .base import AgentResult, LogEntry

__all__ = ['AgentResult', 'LogEntry']
