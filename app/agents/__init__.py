# app/agents/__init__.py
"""
AI research agents for automated data gathering and enrichment.

Each agent module exposes:
    run(record_id, *, dry_run=False) -> AgentResult  — CLI entry point
    research(name, existing_record)  -> AgentResult  — Admin UI entry point (agency only)

CLI:
    flask agent run agency --id 42
    flask agent run vendor --name "Cubic Transportation Systems"
    flask agent run agency --all --dry-run
"""

from .utils import AgentResult, LogEntry

__all__ = ['AgentResult', 'LogEntry']
